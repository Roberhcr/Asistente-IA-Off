"""
voz.py - Motor de voz de Oddye

Qué hace distinto al método anterior (python -m piper por cada respuesta):

  1. Carga Piper UNA sola vez (en segundo plano al abrir la app) y lo deja
     en memoria. Antes se cargaba el modelo "high" completo en cada frase.
  2. Habla por frases: sintetiza la frase 2 mientras suena la frase 1.
     La primera frase empieza a sonar casi de inmediato.
  3. Limpia el texto antes de hablar (sin asteriscos, emojis, viñetas,
     enlaces ni bloques de código) para que no suene a robot leyendo
     símbolos.
  4. Recorta el silencio al inicio/final de cada frase y pone pausas
     naturales y cortas entre ellas (antes había ~0.7 s muertos entre
     frases).
  5. Sin archivos WAV intermedios: el audio va de Piper a la bocina.

Requiere: piper-tts 1.6.0 (el .whl que ya tienes), numpy, sounddevice.
"""

import os
import re
import queue
import threading

import numpy as np

try:
    import sounddevice as sd
except Exception:  # pragma: no cover
    sd = None

PIPER_DISPONIBLE = False
PiperVoice = None
SynthesisConfig = None
_ERROR_IMPORT = ""

try:
    from piper import PiperVoice

    PIPER_DISPONIBLE = True

    try:
        from piper import SynthesisConfig
    except Exception:
        SynthesisConfig = None

except Exception as _error:  # pragma: no cover
    _ERROR_IMPORT = str(_error)


# ============================================================
# LIMPIEZA DE TEXTO PARA HABLAR
# ============================================================

_RE_EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "☀-➿"
    "⬀-⯿"
    "️‍"
    "]+",
    flags=re.UNICODE
)

# Fin de frase confirmado: signo seguido de espacio, o salto de línea.
_RE_FIN_FRASE = re.compile(r"[\.\!\?…](?=\s)|\n")


def limpiar_para_voz(texto):

    if not texto:
        return ""

    t = texto

    # Bloques de razonamiento internos
    t = re.sub(r"<think>.*?</think>", " ", t, flags=re.S | re.I)

    # Código: no se lee, se avisa
    t = re.sub(
        r"```.*?```",
        " Te dejé el código en el chat. ",
        t,
        flags=re.S
    )
    t = re.sub(r"`([^`]*)`", r"\1", t)

    # Enlaces
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"https?://\S+|www\.\S+", " enlace ", t)

    # Emojis
    t = _RE_EMOJI.sub("", t)

    # Markdown de inicio de línea
    t = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", t)
    t = re.sub(r"(?m)^\s*>\s?", "", t)
    t = re.sub(r"(?m)^\s*[-*•+]\s+", "", t)
    t = re.sub(r"(?m)^\s*\d+[\.\)](?:\s+|$)", "", t)

    # Énfasis y símbolos que el TTS leería o rompería
    t = re.sub(r"[*~|]+", "", t)
    t = t.replace("_", " ")
    t = re.sub(r"\s*(->|=>|→)\s*", ", ", t)
    t = t.replace("%", " por ciento")
    t = t.replace("&", " y ")

    # Cada línea es una idea: si no termina en puntuación, se cierra
    lineas = []

    for linea in t.splitlines():

        linea = linea.strip()

        if not linea:
            continue

        if linea[-1] not in ".!?…:;,":
            linea += "."

        lineas.append(linea)

    t = " ".join(lineas)

    t = re.sub(r"\s+", " ", t).strip()

    # Si lo único que quedó son signos, no hay nada que decir
    if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]", t):
        return ""

    return t


def dividir_en_frases(texto, min_chars=18, max_chars=220):

    bruto = re.split(r"(?<=[\.\!\?…])\s+", texto)

    frases = []
    acumulado = ""

    for parte in bruto:

        parte = parte.strip()

        if not parte:
            continue

        acumulado = (
            (acumulado + " " + parte).strip()
            if acumulado else parte
        )

        if len(acumulado) >= min_chars:
            frases.append(acumulado)
            acumulado = ""

    if acumulado:

        # Un resto muy corto se pega a la frase anterior
        if frases and len(acumulado) < min_chars:
            frases[-1] = frases[-1] + " " + acumulado
        else:
            frases.append(acumulado)

    # Frases larguísimas se cortan en una coma o espacio
    salida = []

    for frase in frases:

        while len(frase) > max_chars:

            corte = frase.rfind(",", 0, max_chars)

            if corte < 60:
                corte = frase.rfind(" ", 0, max_chars)

            if corte <= 0:
                corte = max_chars

            salida.append(frase[:corte + 1].strip())
            frase = frase[corte + 1:].strip()

        if frase:
            salida.append(frase)

    return salida


def _recortar_silencio(audio, sr, umbral=0.012, margen_ms=35):

    if audio.size == 0:
        return audio

    activos = np.where(np.abs(audio) > umbral)[0]

    if activos.size == 0:
        return audio[: int(sr * 0.05)]

    margen = int(sr * margen_ms / 1000)

    inicio = max(0, activos[0] - margen)
    fin = min(audio.size, activos[-1] + margen)

    recorte = audio[inicio:fin].copy()

    # Fundidos de 8 ms para evitar "clics" entre frases
    f = min(int(sr * 0.008), recorte.size // 2)

    if f > 0:

        rampa = np.linspace(0, 1, f, dtype=np.float32)

        recorte[:f] *= rampa
        recorte[-f:] *= rampa[::-1]

    return recorte


# ============================================================
# MOTOR DE VOZ
# ============================================================

class MotorVoz:

    def __init__(
        self,
        modelo,
        config=None,
        length_scale=0.93,
        noise_scale=0.72,
        noise_w=0.90,
        pausa_frase=0.16,
        recortar_silencio=True,
        dispositivo_salida=None,
        al_evento=None,
        al_frase=None
    ):

        self.modelo = modelo
        self.config = config

        # length_scale: menor = más rápido (1.0 = velocidad original)
        # noise_scale : mayor = más expresiva / menos monótona
        # noise_w     : mayor = ritmo más variable y humano
        self.length_scale = length_scale
        self.noise_scale = noise_scale
        self.noise_w = noise_w

        self.pausa_frase = pausa_frase
        self.recortar_silencio = recortar_silencio
        self.dispositivo_salida = dispositivo_salida
        self._al_evento = al_evento

        # al_frase(texto, duracion_seg): se llama justo cuando empieza
        # a sonar cada frase (para mostrar el texto al unísono).
        self._al_frase = al_frase

        self._voz = None
        self._sr = 22050

        self._listo = threading.Event()
        self._carga_terminada = threading.Event()
        self.error_carga = None

        self._lock = threading.Lock()
        self._gen = 0
        self._buf = ""

        self._q_texto = queue.Queue()
        self._q_audio = queue.Queue()

        self._iniciado = False
        self._cerrado = False
        self._hablando = False


    # --------------------------------------------------------
    # Estado
    # --------------------------------------------------------

    @property
    def listo(self):
        return self._listo.is_set()

    @property
    def hablando(self):
        return self._hablando


    def _evento(self, nombre, mensaje=""):

        if self._al_evento is None:
            return

        try:
            self._al_evento(nombre, mensaje)
        except Exception as error:
            print("[Voz] Error en callback de evento:", error)


    # --------------------------------------------------------
    # Arranque
    # --------------------------------------------------------

    def iniciar(self):

        with self._lock:

            if self._iniciado:
                return

            self._iniciado = True

        threading.Thread(
            target=self._cargar,
            daemon=True
        ).start()

        threading.Thread(
            target=self._bucle_sintesis,
            daemon=True
        ).start()

        threading.Thread(
            target=self._bucle_reproduccion,
            daemon=True
        ).start()


    def _cargar(self):

        try:

            if not PIPER_DISPONIBLE:
                raise RuntimeError(
                    "No se pudo importar piper: " + _ERROR_IMPORT
                )

            if sd is None:
                raise RuntimeError("sounddevice no está disponible.")

            if not os.path.isfile(self.modelo):
                raise RuntimeError(
                    f"No encontré el modelo de Piper: {self.modelo}"
                )

            self._voz = PiperVoice.load(
                self.modelo,
                config_path=self.config
            )

            self._sr = int(self._voz.config.sample_rate)

            # Calentamiento: la primera síntesis siempre es la lenta.
            self._sintetizar("Hola.")

            self._listo.set()

            print("[Voz] Motor de voz listo (Piper en memoria).")

        except Exception as error:

            self.error_carga = str(error)

            print("[Voz] No se pudo cargar el motor de voz:", error)

        finally:

            self._carga_terminada.set()


    def cerrar(self):

        self._cerrado = True

        self.detener()

        self._q_texto.put(None)
        self._q_audio.put(None)


    # --------------------------------------------------------
    # API pública
    # --------------------------------------------------------

    def hablar(self, texto):
        """Dice un texto completo (cancela lo que esté sonando)."""

        self.comenzar_turno()
        self._encolar(texto)
        self.terminar_turno()


    def comenzar_turno(self):
        """Cancela lo que suene y prepara una respuesta nueva."""

        self.detener()

        with self._lock:
            self._buf = ""

        self._evento("iniciando")


    def agregar_fragmento(self, fragmento):
        """Recibe texto a medida que el cerebro lo genera."""

        if not fragmento:
            return

        with self._lock:

            self._buf += fragmento

            # Dentro de un bloque de código: esperar a que cierre
            if self._buf.count("```") % 2 == 1:
                return

            ultimo = None

            for m in _RE_FIN_FRASE.finditer(self._buf):
                ultimo = m

            if ultimo is None:
                return

            completo = self._buf[:ultimo.end()]
            self._buf = self._buf[ultimo.end():]

        self._encolar(completo)


    def terminar_turno(self):
        """Dice lo que quedó pendiente y marca el fin de la respuesta."""

        with self._lock:
            resto = self._buf
            self._buf = ""

        if resto.strip():
            self._encolar(resto)

        self._q_texto.put((self._gen, None))


    def detener(self):
        """Corta la voz inmediatamente."""

        with self._lock:
            self._gen += 1
            gen = self._gen
            self._buf = ""

        for cola in (self._q_texto, self._q_audio):

            try:
                while True:
                    cola.get_nowait()
            except queue.Empty:
                pass

        self._q_audio.put(("cancelar", gen, None))


    # --------------------------------------------------------
    # Internos
    # --------------------------------------------------------

    def _encolar(self, texto_crudo):

        limpio = limpiar_para_voz(texto_crudo)

        if not limpio:
            return

        for frase in dividir_en_frases(limpio):
            self._q_texto.put((self._gen, frase))


    def _sintetizar(self, texto):

        cfg = None

        if SynthesisConfig is not None:

            cfg = SynthesisConfig(
                length_scale=self.length_scale,
                noise_scale=self.noise_scale,
                noise_w_scale=self.noise_w
            )

        partes = []

        for trozo in self._voz.synthesize(texto, syn_config=cfg):

            arreglo = getattr(trozo, "audio_float_array", None)

            if arreglo is None:
                arreglo = (
                    trozo.audio_int16_array.astype(np.float32) / 32768.0
                )

            partes.append(
                np.asarray(arreglo, dtype=np.float32).reshape(-1)
            )

        if not partes:
            return np.zeros(0, dtype=np.float32)

        audio = np.concatenate(partes)

        if self.recortar_silencio:
            audio = _recortar_silencio(audio, self._sr)

        return audio


    def _bucle_sintesis(self):

        while not self._cerrado:

            item = self._q_texto.get()

            if item is None:
                return

            gen, texto = item

            if gen != self._gen:
                continue

            if texto is None:
                self._q_audio.put(("fin", gen, None))
                continue

            self._carga_terminada.wait()

            if not self._listo.is_set():
                self._evento("error", self.error_carga or "Voz no lista.")
                continue

            try:
                audio = self._sintetizar(texto)

            except Exception as error:
                self._evento("error", str(error))
                continue

            if gen != self._gen:
                continue

            self._q_audio.put(("audio", gen, (audio, texto)))


    def _abrir_stream(self):

        try:

            stream = sd.OutputStream(
                samplerate=self._sr,
                channels=1,
                dtype="float32",
                device=self.dispositivo_salida
            )

            stream.start()

            return stream

        except Exception as error:

            self._evento("error", f"No pude abrir la salida de audio: {error}")

            return None


    def _cerrar_stream(self, stream, abortar):

        if stream is None:
            return None

        try:
            if abortar:
                stream.abort()
            else:
                stream.stop()
        except Exception:
            pass

        try:
            stream.close()
        except Exception:
            pass

        return None


    def _escribir(self, stream, datos, gen):

        paso = max(1, int(self._sr * 0.1))

        for i in range(0, len(datos), paso):

            if gen != self._gen:
                return False

            try:
                stream.write(datos[i:i + paso].reshape(-1, 1))

            except Exception as error:
                self._evento("error", str(error))
                return False

        return True


    def _set_hablando(self, valor):

        antes = self._hablando
        self._hablando = valor

        if valor and not antes:
            self._evento("hablando")

        elif antes and not valor:
            self._evento("terminado")


    def _bucle_reproduccion(self):

        stream = None

        while not self._cerrado:

            item = self._q_audio.get()

            if item is None:
                break

            tipo, gen, datos = item

            if tipo == "cancelar":
                stream = self._cerrar_stream(stream, abortar=True)
                self._set_hablando(False)
                continue

            if gen != self._gen:
                stream = self._cerrar_stream(stream, abortar=True)
                continue

            if tipo == "audio":

                if stream is None:

                    stream = self._abrir_stream()

                    if stream is None:
                        continue

                    self._set_hablando(True)

                audio, texto_frase = datos

                if self._al_frase is not None:

                    try:
                        self._al_frase(
                            texto_frase,
                            len(audio) / float(self._sr)
                        )
                    except Exception as error:
                        print("[Voz] Error en callback de frase:", error)

                if not self._escribir(stream, audio, gen):
                    continue

                pausa = np.zeros(
                    int(self._sr * self.pausa_frase),
                    dtype=np.float32
                )

                self._escribir(stream, pausa, gen)

            elif tipo == "fin":

                stream = self._cerrar_stream(stream, abortar=False)

                if self._hablando:
                    self._set_hablando(False)
                else:
                    self._evento("terminado")

                # Terminó de decir TODA la respuesta de este turno.
                self._evento("turno_completo")

        self._cerrar_stream(stream, abortar=True)