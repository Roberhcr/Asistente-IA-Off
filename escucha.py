"""
escucha.py - Oddye siempre atento (tipo Alexa)

Deja el micrófono abierto, separa lo que dices en frases (por silencios)
y le pasa cada frase a Whisper. Si en la frase aparece el nombre
"Oddye" (aunque Whisper lo escriba "Odie", "Ody", "Oddy"...), Oddye
se activa:

  - "Oddye, abre Word"   -> ejecuta "abre Word" directamente.
  - "Oddye"  (solo)      -> suena un tono y te escucha la siguiente frase.

Todo es offline: usa el mismo servidor de Whisper que ya tienes.

Uso (lo hace main.py):

    escucha = EscuchaNombre(
        transcribir=servidor.transcribir,   # audio float32 16 kHz -> texto
        al_nombre=...,                      # (restante: str) -> None
        al_comando=...,                     # (texto: str) -> None
        pausado=lambda: False,              # True mientras Oddye habla, etc.
        al_estado=...,                      # ("escuchando", ...) opcional
    )
    escucha.iniciar()
"""

import re
import time
import queue
import difflib
import threading
import unicodedata

import numpy as np

try:
    import sounddevice as sd
except Exception:  # pragma: no cover
    sd = None


# ============================================================
# DETECCIÓN DEL NOMBRE
# ============================================================

# Cómo suele escribir Whisper "Oddye" en español (ya normalizado).
_ALIAS = {
    "oddye", "oddie", "oddy", "oddi", "odie", "ody", "odi", "odye",
    "odye", "odai", "odei", "odey", "oddai", "oddei", "oddey",
    "hody", "hodie", "hodi", "oti", "otie", "ordie", "ordi", "audi",
    "audie", "oddis", "odis", "odys", "odies",
    "eddie", "eddy", "edie", "edy", "edi", "oddye", "odd", "oddi",
    "uddi", "oddis", "oldi", "oddie", "oddies",
}

# Forma general: [h]+vocal(es)+d(d)+(i|y)(e)  -> odie, oddy, eddie, hody...
_RE_NOMBRE = re.compile(r"^h?[aeou]{1,2}d{1,2}[iy]e?s?$")

# Si después de algo que "suena parecido" viene un verbo de orden,
# se acepta como nombre aunque Whisper lo haya escrito raro.
_VERBOS = {
    "abre", "abrir", "abreme", "cierra", "cerrar", "cierrame", "pon",
    "ponme", "quita", "busca", "buscame", "dime", "dame", "muestra",
    "muestrame", "sube", "baja", "silencia", "activa", "desactiva",
    "apaga", "enciende", "reproduce", "pausa", "para", "detente",
    "minimiza", "maximiza", "cambia", "crea", "crear", "borra",
    "elimina", "guarda", "escribe", "lee", "que", "cual", "como",
    "cuanto", "cuantos", "cuando", "donde", "quien", "ayudame",
    "explicame", "cuentame", "recuerdame", "inicia", "ejecuta",
    "lanza", "mueve", "copia", "pega", "captura", "toma", "hazme",
    "haz", "necesito", "quiero", "puedes", "podrias", "hola",
}

# Palabras reales que se parecen y NO deben activar a Oddye.
_NO_ES_EL_NOMBRE = {
    "odio", "odia", "odias", "odian", "odiar", "odiado",
    "ocio", "oido", "oidos", "ahora", "otro", "otra", "todo", "toda",
    "orden", "ordenes", "ordeno", "oye", "oyes", "hoy", "ojo", "ojos",
    "ido", "idos",
}

# Muletillas que pueden ir antes del nombre: "oye Oddye", "hey Oddye".
_PREFIJOS = {"oye", "oie", "hey", "ey", "eh", "ok", "okay", "hola", "ah", "oh", "o", "a", "e"}

# Cuántas palabras al inicio se revisan buscando el nombre.
_PALABRAS_BUSQUEDA = 4


def _normalizar(texto):

    texto = unicodedata.normalize("NFD", (texto or "").lower())

    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _clave_fonetica(palabra):

    # "oddye" -> "odi", "hodie" -> "odi", "oddy" -> "odi"
    p = re.sub(r"[^a-z]", "", palabra)
    p = p.replace("h", "")
    p = re.sub(r"(.)\1+", r"\1", p)
    p = p.replace("y", "i")
    p = re.sub(r"ie$", "i", p)
    p = re.sub(r"ei$", "i", p)
    p = re.sub(r"ai$", "i", p)

    return p


def _es_nombre(palabra):

    if palabra in _NO_ES_EL_NOMBRE:
        return False

    if palabra in _ALIAS or _RE_NOMBRE.match(palabra):
        return True

    if not (2 <= len(palabra) <= 7):
        return False

    clave = _clave_fonetica(palabra)

    if clave in {"odi", "odis"}:
        return True

    if len(clave) >= 3 and clave[0] in "oau":
        return difflib.SequenceMatcher(None, clave, "odi").ratio() >= 0.8

    return False


def _suena_parecido(palabra):

    # Más permisivo que _es_nombre: solo se usa si viene un verbo
    # de orden después (ver buscar_nombre).
    if palabra in _NO_ES_EL_NOMBRE or palabra in _VERBOS:
        return False

    if not (2 <= len(palabra) <= 7):
        return False

    clave = _clave_fonetica(palabra)

    if len(clave) < 2 or clave[0] not in "oaeu":
        return False

    return difflib.SequenceMatcher(None, clave, "odi").ratio() >= 0.66


def buscar_nombre(texto):
    """
    Devuelve (encontrado, restante).

    El nombre solo cuenta si está al inicio de la frase (como "Alexa,
    ..."), para no activarse cuando alguien habla DE Oddye. "restante"
    es lo que se dijo después del nombre, ya limpio.
    """

    norm = _normalizar(texto)

    # Palabras con su posición, para poder cortar el texto original.
    palabras = list(re.finditer(r"[a-zñ0-9]+", norm))

    limite = min(len(palabras), _PALABRAS_BUSQUEDA)

    for i in range(limite):

        palabra = palabras[i].group()

        # Los prefijos se saltan solo si van ANTES del nombre.
        if i > 0 and not all(
            palabras[j].group() in _PREFIJOS for j in range(i)
        ):
            break

        fin = None

        if _es_nombre(palabra) and (
            i == 0 or palabras[i - 1].group() in _PREFIJOS
        ):
            fin = palabras[i].end()

        # Whisper a veces separa: "o die", "oh di".
        elif (
            i + 1 < len(palabras)
            and palabra in ("o", "oh", "ho", "au", "oda", "od")
            and _es_nombre(palabra + palabras[i + 1].group())
        ):
            fin = palabras[i + 1].end()

        if fin is not None:

            restante = texto[fin:] if len(texto) == len(norm) else norm[fin:]
            restante = re.sub(r"^[\s,.:;!¡?¿\-–—]+", "", restante)
            restante = re.sub(r"\s+", " ", restante).strip()

            return True, restante

    # ---- Segunda oportunidad: algo que suena parecido + una orden ----
    # "Odi abre Word", "Oli, qué hora es", o la palabra sola ("Oli").
    for i in range(min(len(palabras), 3)):

        if i > 0 and palabras[i - 1].group() not in _PREFIJOS:
            break

        if not _suena_parecido(palabras[i].group()):
            continue

        siguientes = palabras[i + 1:]

        if (not siguientes and len(palabras) <= 2) or (
            siguientes and siguientes[0].group() in _VERBOS
        ):

            fin = palabras[i].end()
            restante = texto[fin:] if len(texto) == len(norm) else norm[fin:]
            restante = re.sub(r"^[\s,.:;!¡?¿\-–—]+", "", restante)
            restante = re.sub(r"\s+", " ", restante).strip()

            return True, restante

    return False, ""


# Whisper inventa estas frases cuando oye ruido o silencio.
_ALUCINACIONES = (
    "subtitulos", "gracias por ver", "suscribete", "amara.org",
    "musica", "aplausos", "hasta la proxima", "hasta el proximo",
    "dejen sus comentarios", "no olvides suscribirte", "like y suscri",
    "traduccion", "subtitulado", "www.", ".com", "se el primero",
    "nos vemos en el proximo", "chao chao", "silencio",
)


def _es_alucinacion(texto, dur=None):

    n = _normalizar(texto)

    if any(a in n for a in _ALUCINACIONES):
        return True

    palabras = re.findall(r"[a-zñ0-9]+", n)

    if not palabras:
        return True

    # Mismas palabras repetidas una y otra vez ("sí sí sí sí").
    if len(palabras) >= 4 and len(set(palabras)) <= max(1, len(palabras) // 4):
        return True

    # Demasiadas letras para tan poco audio: Whisper inventó texto.
    if dur and len("".join(palabras)) / max(dur, 0.1) > 28:
        return True

    return False


# Whisper suele pegar esto al final de frases cortas.
_COLA_INVENTADA = re.compile(
    r"(?:[\s.,!?¡¿]+(?:muchas\s+)?gracias(?:\s+por\s+(?:ver|escuchar)[^.]*)?"
    r"|[\s.,!?¡¿]+hasta\s+(?:la|el)\s+pr[oó]xim[ao][^.]*"
    r"|[\s.,!?¡¿]+subt[ií]tulos[^.]*)+[\s.!?]*$",
    re.IGNORECASE,
)


def limpiar_cola(texto):

    limpio = _COLA_INVENTADA.sub("", texto).strip(" ,.;")

    return limpio if len(limpio) >= 2 else texto


# ============================================================
# TONO DE ACTIVACIÓN
# ============================================================

def _tono_activacion(frecuencia_hz=16000):

    # Dos notas cortas y suaves (sube = "te escucho").
    def nota(f, dur):
        t = np.arange(int(frecuencia_hz * dur)) / frecuencia_hz
        env = np.sin(np.pi * t / dur) ** 2
        return 0.22 * env * np.sin(2 * np.pi * f * t)

    return np.concatenate([nota(660, 0.09), nota(880, 0.12)]).astype("float32")


# ============================================================
# ESCUCHA
# ============================================================

class EscuchaNombre:

    FS = 16000
    BLOQUE = 480  # 30 ms

    def __init__(
        self,
        transcribir,
        al_nombre=None,
        al_comando=None,
        pausado=None,
        al_estado=None,
        dispositivo=None,
        umbral_minimo=0.012,
        silencio_fin_seg=0.7,
        max_frase_seg=10.0,
        espera_comando_seg=7.0,
        pausa_extra_seg=0.7,
        sonido=True,
        log_ruta=None,
        ignorar=(),
    ):

        self._transcribir = transcribir
        self._al_nombre = al_nombre
        self._al_comando = al_comando
        self._pausado = pausado or (lambda: False)
        self._al_estado = al_estado

        self.dispositivo = dispositivo
        self.umbral_minimo = umbral_minimo
        self.silencio_fin_seg = silencio_fin_seg
        self.max_frase_seg = max_frase_seg
        self.espera_comando_seg = espera_comando_seg
        self.pausa_extra_seg = pausa_extra_seg
        self.sonido = sonido
        self.log_ruta = log_ruta

        # Frases que Whisper repite del "prompt" cuando oye silencio.
        self._ignorar = {
            re.sub(r"[^a-zñ0-9 ]", "", _normalizar(t)).strip()
            for t in ignorar if t
        }

        self._stream = None
        self._cola_bloques = queue.Queue(maxsize=400)
        self._cola_frases = queue.Queue(maxsize=4)

        self._activa = False
        self._hilo_vad = None
        self._hilo_asr = None

        # "espera_nombre" | "espera_comando"
        self._modo = "espera_nombre"
        self._limite_comando = 0.0
        self._lock = threading.Lock()

        self._ocupada = False  # procesando un comando (no escuchar encima)
        self._hablando_vad = False


    # --------------------------------------------------------
    # Control
    # --------------------------------------------------------

    @property
    def activa(self):
        return self._activa


    def iniciar(self):

        if self._activa:
            return True

        if sd is None:
            print("[Escucha] sounddevice no está disponible.")
            return False

        # Colas nuevas: si se había detenido, no quedan señales viejas.
        self._cola_bloques = queue.Queue(maxsize=400)
        self._cola_frases = queue.Queue(maxsize=4)
        self._modo = "espera_nombre"
        self._ocupada = False
        self._hablando_vad = False

        try:

            self._stream = sd.InputStream(
                samplerate=self.FS,
                channels=1,
                dtype="float32",
                blocksize=self.BLOQUE,
                device=self.dispositivo,
                callback=self._callback,
            )

            self._stream.start()

        except Exception as error:

            self._stream = None
            print(f"[Escucha] No se pudo abrir el micrófono: {error}")
            return False

        self._activa = True

        self._hilo_vad = threading.Thread(target=self._bucle_vad, daemon=True)
        self._hilo_asr = threading.Thread(target=self._bucle_asr, daemon=True)
        self._hilo_vad.start()
        self._hilo_asr.start()

        print('[Escucha] Atenta. Di "Oddye".')

        return True


    def detener(self):

        self._activa = False

        try:

            if self._stream is not None:
                self._stream.stop()
                self._stream.close()

        except Exception:
            pass

        self._stream = None

        # Despierta los hilos para que terminen.
        for q in (self._cola_bloques, self._cola_frases):
            try:
                q.put_nowait(None)
            except queue.Full:
                pass


    def ocupada(self, valor):

        # main.py avisa mientras procesa un comando por voz.
        self._ocupada = bool(valor)

        if not valor:
            self._modo = "espera_nombre"


    def esperar_comando(self):

        with self._lock:
            self._modo = "espera_comando"
            self._limite_comando = time.time() + self.espera_comando_seg

        self._estado("esperando_orden")

        # Si nadie dice nada, la interfaz vuelve a "lista".
        threading.Timer(
            self.espera_comando_seg + 0.4,
            self._revisar_ventana
        ).start()


    def _revisar_ventana(self):

        # Solo avisa a la interfaz; el modo lo decide la hora en que
        # empezó a hablar cada frase (ver _procesar_frase).
        if (
            self._modo == "espera_comando"
            and time.time() > self._limite_comando
            and not self._hablando_vad
            and self._cola_frases.empty()
        ):
            self._modo = "espera_nombre"
            self._estado("reposo")


    def _estado(self, nombre):

        if self._al_estado is not None:

            try:
                self._al_estado(nombre)
            except Exception:
                pass


    # --------------------------------------------------------
    # Captura y detección de frases (energía adaptativa)
    # --------------------------------------------------------

    def _callback(self, indata, frames, tiempo, status):

        try:
            self._cola_bloques.put_nowait(indata[:, 0].copy())
        except queue.Full:
            pass


    def _bucle_vad(self):

        bloques_silencio_fin = int(self.silencio_fin_seg * self.FS / self.BLOQUE)
        bloques_max = int(self.max_frase_seg * self.FS / self.BLOQUE)
        bloques_pre = 16  # ~480 ms antes: no se corta la "O" de Oddye

        pre = []
        frase = []
        hablando = False
        en_silencio = 0
        arranque = 0
        t_inicio = 0.0
        con_voz = 0  # bloques de la frase que sí tienen voz
        piso = 0.004  # ruido de fondo estimado
        pausa_hasta = 0.0

        while self._activa:

            bloque = self._cola_bloques.get()

            if bloque is None:
                break

            # No oírse a sí misma ni mientras procesa un comando.
            if self._ocupada or self._pausado():

                pre.clear()
                frase.clear()
                hablando = False
                self._hablando_vad = False
                arranque = 0
                pausa_hasta = time.time() + self.pausa_extra_seg
                continue

            if time.time() < pausa_hasta:
                continue

            rms = float(np.sqrt(np.mean(bloque * bloque)))

            umbral = max(self.umbral_minimo, min(piso * 2.5, 0.03))

            if not hablando:

                # El piso solo se actualiza con silencio.
                piso = 0.98 * piso + 0.02 * min(rms, 0.05)

                pre.append(bloque)

                if len(pre) > bloques_pre:
                    pre.pop(0)

                if rms > umbral:
                    arranque += 1
                else:
                    arranque = 0

                if arranque >= 2:

                    hablando = True
                    self._hablando_vad = True
                    t_inicio = time.time()
                    con_voz = arranque
                    frase = list(pre)
                    pre.clear()
                    en_silencio = 0

                continue

            frase.append(bloque)

            if rms > umbral * 0.7:
                en_silencio = 0
                con_voz += 1
            else:
                en_silencio += 1

            if en_silencio >= bloques_silencio_fin or len(frase) >= bloques_max:

                audio = np.concatenate(frase)

                hablando = False
                self._hablando_vad = False
                arranque = 0
                frase = []
                pre.clear()

                # Un golpe o un clic dura pocos bloques: se descarta.
                if con_voz >= 8:
                    self._enviar_frase(audio, t_inicio)


    def _enviar_frase(self, audio, t_inicio):

        dur = len(audio) / self.FS

        # Demasiado corta (un golpe, un clic) o sin energía real.
        if dur < 0.35:
            return

        if float(np.max(np.abs(audio))) < 0.03:
            return

        try:
            self._cola_frases.put_nowait((audio, t_inicio))
        except queue.Full:
            # Whisper va atrasado: descarta la más vieja.
            try:
                self._cola_frases.get_nowait()
                self._cola_frases.put_nowait((audio, t_inicio))
            except Exception:
                pass


    # --------------------------------------------------------
    # Reconocimiento
    # --------------------------------------------------------

    def _preparar_audio(self, audio, relleno_seg=0.3):

        audio = audio.astype("float32")

        # Quita el desnivel de corriente continua del micrófono.
        audio = audio - float(np.mean(audio))

        pico = float(np.max(np.abs(audio)))

        if pico > 0:
            audio = audio * (0.9 / pico)

        # Un poco de silencio alrededor ayuda a Whisper con frases muy cortas.
        pad = np.zeros(int(relleno_seg * self.FS), dtype="float32")

        return np.concatenate([pad, audio, pad])


    def _log(self, dur, pico, texto, resultado):

        if not self.log_ruta:
            return

        try:

            import os

            if (
                os.path.isfile(self.log_ruta)
                and os.path.getsize(self.log_ruta) > 300_000
            ):
                os.replace(self.log_ruta, self.log_ruta + ".viejo")

            with open(self.log_ruta, "a", encoding="utf-8") as f:
                f.write(
                    f"{time.strftime('%H:%M:%S')} | {dur:4.1f}s | "
                    f"pico {pico:.3f} | {resultado:<10} | {texto}\n"
                )

        except Exception:
            pass


    def _reconocer(self, audio, buscar):

        # Whisper con frases muy cortas ("Oddye" solo) falla más.
        # Si no sale el nombre, se reintenta con más silencio alrededor.
        dur = len(audio) / self.FS

        texto = (self._transcribir(self._preparar_audio(audio)) or "").strip()

        if not buscar or dur > 1.8:
            return texto

        if texto and not _es_alucinacion(texto, dur) and buscar_nombre(texto)[0]:
            return texto

        if self._ocupada or self._pausado():
            return texto

        segundo = (
            self._transcribir(self._preparar_audio(audio, 0.7)) or ""
        ).strip()

        if segundo and not _es_alucinacion(segundo, dur):

            if buscar_nombre(segundo)[0] or not texto:
                return segundo

        return texto


    def _bucle_asr(self):

        while self._activa:

            item = self._cola_frases.get()

            if item is None:
                break

            audio, t_inicio = item

            try:
                self._procesar_frase(audio, t_inicio)
            except Exception as error:
                print(f"[Escucha] Error procesando una frase: {error}")

            self._revisar_ventana()


    def _procesar_frase(self, audio, t_inicio):

        if self._ocupada or self._pausado():
            return

        dur = len(audio) / self.FS
        pico = float(np.max(np.abs(audio)))

        try:
            texto = self._reconocer(audio, self._modo == "espera_nombre")
        except Exception as error:
            print(f"[Escucha] Whisper no respondió: {error}")
            return

        if not texto:
            self._log(dur, pico, "", "vacío")
            return

        if _es_alucinacion(texto, dur):
            self._log(dur, pico, texto, "alucinó")
            return

        eco = re.sub(r"[^a-zñ0-9 ]", "", _normalizar(texto)).strip()

        if eco in self._ignorar and self._modo == "espera_nombre":
            self._log(dur, pico, texto, "eco")
            return

        # Mientras Whisper pensaba, pudo empezar otra cosa.
        if self._ocupada or self._pausado():
            return

        with self._lock:
            modo = self._modo
            limite = self._limite_comando

        # ---- Esperando la orden después de "Oddye" ----
        if modo == "espera_comando":

            with self._lock:
                self._modo = "espera_nombre"

            # Vale si empezó a hablar dentro de la ventana de espera.
            if t_inicio <= limite:

                # Si repite el nombre, se lo quitamos.
                repite, resto = buscar_nombre(texto)
                orden = limpiar_cola(resto if repite else texto)

                if orden:
                    self._log(dur, pico, texto, "comando")
                    print(f"[Escucha] Comando: {orden}")
                    self._lanzar_comando(orden)

                return

        # ---- Esperando el nombre ----
        encontrado, restante = buscar_nombre(texto)

        if not encontrado:
            self._log(dur, pico, texto, "ignorado")
            print(f"[Escucha] (ignorado) {texto}")
            return

        self._log(dur, pico, texto, "NOMBRE")
        print(f"[Escucha] Nombre detectado: {texto}")

        restante = limpiar_cola(restante) if restante else ""

        if restante and len(restante) >= 2:

            self._lanzar_comando(restante)

            return

        # Solo dijo el nombre: aviso y espero la orden.
        self.esperar_comando()

        if self._al_nombre is not None:

            try:
                self._al_nombre("")
            except Exception as error:
                print(f"[Escucha] al_nombre falló: {error}")

        if self.sonido:
            self._sonar()


    def _lanzar_comando(self, orden):

        if self._al_comando is None:
            return

        self._ocupada = True

        def _hacer():

            try:
                self._al_comando(orden)
            except Exception as error:
                print(f"[Escucha] El comando falló: {error}")
            finally:
                self._ocupada = False
                self._modo = "espera_nombre"

        threading.Thread(target=_hacer, daemon=True).start()


    def _sonar(self):

        if sd is None:
            return

        try:
            sd.play(_tono_activacion(self.FS), self.FS, blocking=False)
        except Exception:
            pass