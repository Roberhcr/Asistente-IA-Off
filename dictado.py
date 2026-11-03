"""
dictado.py — Dictado en vivo para Oddye

Qué hace:
  1. ServidorWhisper: arranca whisper-server.exe (whisper.cpp) UNA sola vez,
     con el modelo ya cargado en memoria. Cada frase se manda por HTTP, así
     no se vuelve a cargar el modelo "medium" en cada transcripción
     (esa recarga es lo que hace que tarde tanto con whisper-cli.exe).
  2. DictadoEnVivo: escucha el micrófono, corta el audio en frases cuando
     detecta una pausa y manda cada frase a transcribir mientras sigues
     hablando. El texto va saliendo frase por frase.
  3. limpiar_autocorrecciones: usa Qwen (llama-server) para quedarse con la
     versión final cuando el usuario se corrige a mitad de frase.

Pon este archivo junto a main.py.
"""

import io
import re
import json
import time
import wave
import uuid
import queue
import socket
import threading
import subprocess
import urllib.request
import os

import numpy as np


SAMPLERATE = 16000
BLOQUE = 480                      # 30 ms a 16 kHz
BLOQUES_PRERROLL = 10             # ~300 ms antes de que empiece la voz
BLOQUES_COLA_SILENCIO = 8         # ~240 ms de silencio que se conservan al final
DURACION_MINIMA_FRASE_SEG = 0.4


# ============================================================
# UTILIDADES
# ============================================================

def _a_wav_bytes(audio):
    """float32 mono 16 kHz -> bytes de un WAV PCM_16 en memoria."""

    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767).astype(np.int16)

    buffer = io.BytesIO()

    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLERATE)
        wav.writeframes(pcm.tobytes())

    return buffer.getvalue()


def _multipart(campos, nombre_archivo_campo, nombre_archivo, contenido, tipo):

    limite = "----oddye" + uuid.uuid4().hex
    partes = []

    for clave, valor in campos.items():

        partes.append(
            (
                f"--{limite}\r\n"
                f'Content-Disposition: form-data; name="{clave}"\r\n\r\n'
                f"{valor}\r\n"
            ).encode("utf-8")
        )

    partes.append(
        (
            f"--{limite}\r\n"
            f'Content-Disposition: form-data; name="{nombre_archivo_campo}"; '
            f'filename="{nombre_archivo}"\r\n'
            f"Content-Type: {tipo}\r\n\r\n"
        ).encode("utf-8")
    )
    partes.append(contenido)
    partes.append(f"\r\n--{limite}--\r\n".encode("utf-8"))

    return b"".join(partes), f"multipart/form-data; boundary={limite}"


def _limpiar_texto_whisper(texto):
    """Quita marcas tipo [BLANK_AUDIO] o (música) y espacios de más."""

    texto = re.sub(r"\[[^\]]*\]", " ", texto or "")
    texto = re.sub(r"\([^)]*\)", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


# ============================================================
# SERVIDOR DE WHISPER (modelo cargado una sola vez)
# ============================================================

class ServidorWhisper:

    def __init__(
        self,
        exe,
        modelo,
        hilos,
        prompt="",
        puerto=8081,
        beam_size=2,
        best_of=2,
        no_speech_thold=0.60,
        audio_ctx=0,
    ):

        self.exe = exe
        self.modelo = modelo
        self.hilos = hilos
        self.prompt = prompt
        self.puerto = puerto
        self.beam_size = beam_size
        self.best_of = best_of
        self.no_speech_thold = no_speech_thold

        # 0 = ventana completa de 30 s. 768 = ~15 s (casi el doble de
        # rápido en frases cortas). Con 768 no pases de ~14 s por frase.
        self.audio_ctx = audio_ctx

        self.proceso = None


    def disponible(self):

        return os.path.isfile(self.exe) and os.path.isfile(self.modelo)


    def iniciar(self):
        """Lanza el servidor (no espera a que termine de cargar)."""

        if self.proceso is not None and self.proceso.poll() is None:
            return True

        if not self.disponible():

            print(
                "[Dictado] No encontré whisper-server.exe o el modelo:\n"
                f"  {self.exe}\n  {self.modelo}"
            )

            return False

        comando = [
            self.exe,
            "-m", self.modelo,
            "--host", "127.0.0.1",
            "--port", str(self.puerto),
            "-l", "es",
            "-t", str(self.hilos),
            "-bo", str(self.best_of),
            "-bs", str(self.beam_size),
            "-nth", str(self.no_speech_thold),
        ]

        if self.audio_ctx and self.audio_ctx > 0:
            comando += ["-ac", str(self.audio_ctx)]

        if self.prompt:
            comando += ["--prompt", self.prompt]

        try:

            self.proceso = subprocess.Popen(
                comando,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

            return True

        except Exception as error:

            print(f"[Dictado] No se pudo iniciar whisper-server: {error}")
            self.proceso = None

            return False


    def listo(self, timeout=0.3):
        """True si el servidor ya terminó de cargar y acepta conexiones."""

        if self.proceso is None or self.proceso.poll() is not None:
            return False

        try:

            with socket.create_connection(
                ("127.0.0.1", self.puerto),
                timeout=timeout,
            ):
                return True

        except OSError:

            return False


    def esperar_listo(self, timeout=90):

        inicio = time.time()

        while time.time() - inicio < timeout:

            if self.proceso is None or self.proceso.poll() is not None:
                return False

            if self.listo(timeout=1):
                return True

            time.sleep(0.5)

        return False


    def detener(self):

        proceso = self.proceso
        self.proceso = None

        if proceso is None:
            return

        try:

            if proceso.poll() is None:

                proceso.terminate()

                try:
                    proceso.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proceso.kill()

        except Exception:
            pass


    def transcribir(self, audio):
        """audio: np.float32 mono 16 kHz. Devuelve el texto (str)."""

        cuerpo, tipo = _multipart(
            {
                "response_format": "json",
                "temperature": "0.0",
                "language": "es",
            },
            "file",
            "audio.wav",
            _a_wav_bytes(audio),
            "audio/wav",
        )

        solicitud = urllib.request.Request(
            f"http://127.0.0.1:{self.puerto}/inference",
            data=cuerpo,
            headers={"Content-Type": tipo},
        )

        with urllib.request.urlopen(solicitud, timeout=120) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))

        return _limpiar_texto_whisper(datos.get("text", ""))


# ============================================================
# DICTADO EN VIVO (corta por pausas y transcribe frase a frase)
# ============================================================

class DictadoEnVivo:

    def __init__(
        self,
        servidor,
        al_texto,
        umbral_voz=0.01,
        pausa_seg=0.9,
        max_frase_seg=25,
        dispositivo=None,
        silencio_auto_seg=2.0,
        al_silencio=None,
        al_terminar=None,
    ):

        self.servidor = servidor
        self.al_texto = al_texto

        # Segundos de silencio (después de haber hablado) para que el
        # dictado se detenga solo. 0 = no se detiene solo.
        self.silencio_auto_seg = silencio_auto_seg

        # al_silencio(): se avisa cuando se detiene por silencio.
        # al_terminar(): se avisa cuando ya se entregó TODO el texto.
        self.al_silencio = al_silencio
        self.al_terminar = al_terminar
        self.umbral_voz = umbral_voz
        self.pausa_seg = pausa_seg
        self.max_frase_seg = max_frase_seg
        self.dispositivo = dispositivo

        self.activo = False

        self._stream = None
        self._cola = None
        self._lock = threading.Lock()

        self._reiniciar_estado()


    def _reiniciar_estado(self):

        self._en_frase = False
        self._bloques = []
        self._bloques_silencio = 0
        self._preroll = []

        # Para detenerse solo tras un silencio
        self._hubo_voz = False
        self._bloques_sin_voz = 0
        self._auto_disparado = False


    # --------------------------------------------------------
    # Control
    # --------------------------------------------------------

    def iniciar(self):

        if self.activo:

            return {
                "ok": False,
                "mensaje": "Ya estoy escuchando.",
            }

        try:
            import sounddevice as sd
        except Exception as error:

            return {
                "ok": False,
                "mensaje": f"No se pudo cargar sounddevice: {error}",
            }

        with self._lock:
            self._reiniciar_estado()

        self._cola = queue.Queue()

        threading.Thread(
            target=self._trabajador,
            args=(self._cola,),
            daemon=True,
        ).start()

        try:

            self._stream = sd.InputStream(
                samplerate=SAMPLERATE,
                channels=1,
                dtype="float32",
                blocksize=BLOQUE,
                device=self.dispositivo,
                callback=self._callback,
            )

            self._stream.start()

        except Exception as error:

            self._stream = None
            self._cola.put(None)

            return {
                "ok": False,
                "mensaje": f"No se pudo abrir el micrófono: {error}",
            }

        self.activo = True

        return {"ok": True}


    def detener(self):

        if not self.activo and self._stream is None:
            return {"ok": True}

        self.activo = False

        try:

            if self._stream is not None:
                self._stream.stop()
                self._stream.close()

        except Exception:
            pass

        self._stream = None

        # Lo que quedó a medias se manda igual; luego el trabajador cierra.
        with self._lock:

            if self._en_frase:
                self._cerrar_frase()

        if self._cola is not None:
            self._cola.put(None)

        return {"ok": True}


    # --------------------------------------------------------
    # Audio (hilo del micrófono: debe ser rápido)
    # --------------------------------------------------------

    def _callback(self, indata, frames, time_info, status):

        bloque = indata[:, 0].copy()
        rms = float(np.sqrt(np.mean(np.square(bloque))))

        bloques_pausa = max(
            1,
            int(self.pausa_seg * SAMPLERATE / BLOQUE),
        )

        bloques_max = int(self.max_frase_seg * SAMPLERATE / BLOQUE)

        bloques_auto = (
            int(self.silencio_auto_seg * SAMPLERATE / BLOQUE)
            if self.silencio_auto_seg and self.silencio_auto_seg > 0
            else 0
        )

        with self._lock:

            # ¿Hay voz en este bloque? (con histéresis si ya hablabas)
            hay_voz = rms >= (
                self.umbral_voz * 0.5
                if self._en_frase
                else self.umbral_voz
            )

            if hay_voz:
                self._hubo_voz = True
                self._bloques_sin_voz = 0
            else:
                self._bloques_sin_voz += 1

            if self._en_frase:

                self._bloques.append(bloque)

                # Histéresis: para seguir "hablando" basta la mitad del umbral
                if rms >= self.umbral_voz * 0.5:
                    self._bloques_silencio = 0
                else:
                    self._bloques_silencio += 1

                if (
                    self._bloques_silencio >= bloques_pausa
                    or len(self._bloques) >= bloques_max
                ):
                    self._cerrar_frase()

            else:

                if rms >= self.umbral_voz:

                    self._en_frase = True
                    self._bloques = list(self._preroll) + [bloque]
                    self._bloques_silencio = 0
                    self._preroll = []

                else:

                    self._preroll.append(bloque)
                    self._preroll = self._preroll[-BLOQUES_PRERROLL:]

            # Silencio largo después de haber hablado -> detenerse solo.
            # Se hace en otro hilo: no se puede parar el micrófono desde
            # su propio callback.
            if (
                bloques_auto
                and self._hubo_voz
                and not self._auto_disparado
                and self._bloques_sin_voz >= bloques_auto
            ):

                self._auto_disparado = True

                threading.Thread(
                    target=self._detener_por_silencio,
                    daemon=True,
                ).start()


    def _detener_por_silencio(self):

        print("[Dictado] Silencio detectado: se detiene el dictado.")

        if self.al_silencio is not None:

            try:
                self.al_silencio()
            except Exception as error:
                print(f"[Dictado] Error avisando el silencio: {error}")

        self.detener()


    def _cerrar_frase(self):
        """Llamar con self._lock tomado."""

        bloques = self._bloques
        sobran = max(0, self._bloques_silencio - BLOQUES_COLA_SILENCIO)

        self._en_frase = False
        self._bloques = []
        self._bloques_silencio = 0
        self._preroll = []

        if sobran:
            bloques = bloques[:-sobran]

        if not bloques:
            return

        audio = np.concatenate(bloques)

        if len(audio) / SAMPLERATE < DURACION_MINIMA_FRASE_SEG:
            return

        if self._cola is not None:
            self._cola.put(audio)


    # --------------------------------------------------------
    # Transcripción (hilo aparte)
    # --------------------------------------------------------

    def _trabajador(self, cola):

        while True:

            audio = cola.get()

            if audio is None:
                break

            pico = float(np.max(np.abs(audio)))

            if pico > 0:
                audio = audio * (0.9 / pico)

            inicio = time.time()

            try:
                texto = self.servidor.transcribir(audio)
            except Exception as error:
                print(f"[Dictado] Error transcribiendo frase: {error}")
                continue

            print(
                f"[Dictado] Frase de {len(audio) / SAMPLERATE:.1f}s "
                f"transcrita en {time.time() - inicio:.2f}s: {texto}"
            )

            if texto:

                try:
                    self.al_texto(texto)
                except Exception as error:
                    print(f"[Dictado] Error entregando el texto: {error}")

        # Ya se entregó todo el texto pendiente.
        if self.al_terminar is not None:

            try:
                self.al_terminar()
            except Exception as error:
                print(f"[Dictado] Error avisando el final: {error}")


# ============================================================
# LIMPIEZA DE AUTOCORRECCIONES CON QWEN
# ============================================================

MARCAS_AUTOCORRECCION = (
    " no,", " no ", "perdón", "perdon", "digo", "mejor dicho",
    "quise decir", "quiero decir", "me equivoqué", "me equivoque",
    "espera", "corrección", "correccion", "mejor no", "bueno no",
    "mejor abre", "mejor cierra", "mejor busca",
)

PROMPT_LIMPIEZA = (
    "Eres un corrector de dictados por voz en español. Recibes la "
    "transcripción de lo que dijo una persona. Si la persona se corrige a "
    "mitad de frase, devuelve únicamente la versión final ya corregida, sin "
    "la parte equivocada ni la palabra de corrección. Si no hay "
    "autocorrección, devuelve el texto exactamente igual. No respondas a lo "
    "que dice el texto, no agregues explicaciones, no cambies el "
    "significado y no traduzcas. Devuelve solo el texto resultante.\n\n"
    "Ejemplos:\n"
    "Entrada: abre Chrome, no, abre Word\n"
    "Salida: abre Word\n"
    "Entrada: ábreme la carpeta Descargas, perdón, la carpeta Documentos\n"
    "Salida: ábreme la carpeta Documentos\n"
    "Entrada: qué hora es\n"
    "Salida: qué hora es"
)


def tiene_posible_autocorreccion(texto):

    t = " " + (texto or "").lower() + " "

    return any(marca in t for marca in MARCAS_AUTOCORRECCION)


def limpiar_autocorrecciones(texto, llama_url, forzar=False, timeout=60):
    """
    Devuelve el texto sin autocorrecciones. Si algo falla, devuelve el
    original. Solo llama a Qwen si el texto parece tener una corrección
    (a menos que forzar=True).
    """

    texto = (texto or "").strip()

    if not texto:
        return texto

    if not forzar and not tiene_posible_autocorreccion(texto):
        return texto

    datos = {
        "messages": [
            {"role": "system", "content": PROMPT_LIMPIEZA},
            {"role": "user", "content": texto + " /no_think"},
        ],
        "temperature": 0.1,
        "max_tokens": min(200, max(40, len(texto.split()) * 4)),
    }

    solicitud = urllib.request.Request(
        llama_url + "/v1/chat/completions",
        data=json.dumps(datos).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:

        with urllib.request.urlopen(solicitud, timeout=timeout) as respuesta:
            cuerpo = json.loads(respuesta.read().decode("utf-8"))

        salida = cuerpo["choices"][0]["message"]["content"]

    except Exception as error:

        print(f"[Dictado] No se pudo limpiar el texto: {error}")

        return texto

    salida = re.sub(r"<think>.*?</think>", "", salida, flags=re.S)
    salida = salida.strip().strip('"“”«»').strip()

    # Protección: si Qwen devolvió algo vacío o mucho más largo
    # (por ejemplo, se puso a responder), se queda el texto original.
    if not salida or len(salida) > len(texto) * 1.3 + 10:
        return texto

    return salida