#Modo serio 
import os
import sys
import time
import json
import wave
import queue
import shutil
import tempfile
import subprocess
import urllib.request

import sounddevice as sd
import soundfile as sf


# ============================================================
# CONFIGURACIÓN PRINCIPAL
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Modelos
CEREBRO_MODELO = os.path.join(
    BASE_DIR,
    "Modelos",
    "Cerebro 4B (llama.cpp)",
    "Qwen3-4B-Q4_K_M.gguf"
)

WHISPER_MODELO = os.path.join(
    BASE_DIR,
    "Modelos",
    "Oidos (Whisper Base)",
    "ggml-base.bin"
)

PIPER_MODELO = os.path.join(
    BASE_DIR,
    "Voz (Piper)",
    "es_MX-claude-high.onnx"
)

PIPER_CONFIG = os.path.join(
    BASE_DIR,
    "Voz (Piper)",
    "es_MX-claude-high.onnx.json"
)

# Motores
LLAMA_SERVER = os.path.join(
    BASE_DIR,
    "Motores",
    "Cerebro",
    "llama-b10588-bin-win-cpu-x64",
    "llama-server.exe"
)

WHISPER_EXE = os.path.join(
    BASE_DIR,
    "Motores",
    "Oidos",
    "whisper-bin-x64",
    "Release",
    "whisper-cli.exe"
)

# Servidor
LLAMA_URL = "http://127.0.0.1:8080"

# Audio
SAMPLE_RATE = 16000
CHANNELS = 1

# Archivos temporales
TEMP_DIR = os.path.join(BASE_DIR, "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

GRABACION = os.path.join(TEMP_DIR, "entrada.wav")
RESPUESTA_WAV = os.path.join(TEMP_DIR, "respuesta.wav")


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def comprobar_archivo(ruta, nombre):
    if not os.path.isfile(ruta):
        print(f"❌ No encontrado: {nombre}")
        print(f"   {ruta}")
        return False

    print(f"✓ {nombre}")
    return True


def comprobar_archivos():
    print("=" * 60)
    print("       ASISTENTE AI LOCAL")
    print("=" * 60)
    print()

    archivos = [
        (CEREBRO_MODELO, "Modelo del cerebro"),
        (WHISPER_MODELO, "Modelo Whisper"),
        (PIPER_MODELO, "Modelo Piper"),
        (PIPER_CONFIG, "Configuración Piper"),
        (LLAMA_SERVER, "llama-server"),
        (WHISPER_EXE, "Whisper"),
    ]

    correcto = True

    for ruta, nombre in archivos:
        if not comprobar_archivo(ruta, nombre):
            correcto = False

    print()

    if not correcto:
        print("❌ Faltan archivos necesarios.")
        return False

    print("✓ Todos los componentes principales están presentes.")
    print()

    return True


# ============================================================
# LLAMA SERVER
# ============================================================

servidor = None


def iniciar_cerebro():
    global servidor

    print("🧠 Iniciando cerebro...")

    comando = [
        LLAMA_SERVER,
        "-m",
        CEREBRO_MODELO,
        "--port",
        "8080"
    ]

    try:
        servidor = subprocess.Popen(
            comando,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

    except Exception as e:
        print("❌ No se pudo iniciar llama-server.")
        print(e)
        return False

    print("   Esperando al cerebro...")

    for i in range(30):

        try:
            respuesta = urllib.request.urlopen(
                LLAMA_URL + "/health",
                timeout=1
            )

            if respuesta.status == 200:
                print("✓ Cerebro funcionando.")
                print()
                return True

        except Exception:
            pass

        time.sleep(1)

    print("❌ El cerebro no respondió.")
    return False


# ============================================================
# WHISPER
# ============================================================

def escuchar():

    print("=" * 60)
    print("🎤 ESCUCHANDO")
    print("=" * 60)
    print("Habla durante unos segundos...")
    print("Cuando termines, espera.")
    print()

    try:

        audio = sd.rec(
            int(8 * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32"
        )

        sd.wait()

        sf.write(
            GRABACION,
            audio,
            SAMPLE_RATE,
            subtype="PCM_16"
        )

        print("✓ Audio capturado.")
        print("👂 Whisper está procesando...")

    except Exception as e:
        print("❌ Error capturando audio:")
        print(e)
        return None

    comando = [
        WHISPER_EXE,
        "-m",
        WHISPER_MODELO,
        "-l",
        "es",
        "-f",
        GRABACION
    ]

    try:

        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )

    except Exception as e:
        print("❌ Error ejecutando Whisper:")
        print(e)
        return None

    texto = ""

    for linea in resultado.stdout.splitlines():

        if "-->" in linea and "]" in linea:

            partes = linea.split("]", 1)

            if len(partes) == 2:
                texto += partes[1].strip() + " "

    texto = texto.strip()

    if not texto:

        print("⚠️ No pude entender el audio.")
        return None

    print()
    print("👤 Tú:")
    print(texto)
    print()

    return texto


# ============================================================
# CEREBRO
# ============================================================

def preguntar_cerebro(texto):

    print("🧠 Pensando...")

    datos = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres un asistente de inteligencia artificial local. "
                    "Responde en español de forma natural, clara y concisa."
                )
            },
            {
                "role": "user",
                "content": texto
            }
        ],
        "temperature": 0.7,
        "max_tokens": 200
    }

    cuerpo = json.dumps(datos).encode("utf-8")

    solicitud = urllib.request.Request(
        LLAMA_URL + "/v1/chat/completions",
        data=cuerpo,
        headers={
            "Content-Type": "application/json"
        }
    )

    try:

        respuesta = urllib.request.urlopen(
            solicitud,
            timeout=120
        )

        datos_respuesta = json.loads(
            respuesta.read().decode("utf-8")
        )

        respuesta_texto = datos_respuesta["choices"][0]["message"]["content"]

        return respuesta_texto.strip()

    except Exception as e:

        print("❌ Error comunicando con el cerebro:")
        print(e)

        return None


# ============================================================
# PIPER
# ============================================================

def hablar(texto):

    print()
    print("🗣️ Piper está generando la voz...")

    comando = [
        sys.executable,
        "-m",
        "piper",
        "-m",
        PIPER_MODELO,
        "-c",
        PIPER_CONFIG,
        "-f",
        RESPUESTA_WAV
    ]

    try:

        subprocess.run(
            comando,
            input=texto,
            text=True,
            encoding="utf-8",
            check=True
        )

    except Exception as e:

        print("❌ Error ejecutando Piper:")
        print(e)
        return False

    print("🔊 Reproduciendo respuesta...")

    try:

        audio, frecuencia = sf.read(RESPUESTA_WAV)

        sd.play(
            audio,
            frecuencia
        )

        sd.wait()

    except Exception as e:

        print("❌ Error reproduciendo audio:")
        print(e)
        return False

    return True


# ============================================================
# DETENER SERVIDOR
# ============================================================

def detener_cerebro():

    global servidor

    if servidor is not None:

        print()
        print("🛑 Cerrando cerebro...")

        servidor.terminate()

        try:
            servidor.wait(timeout=5)
        except subprocess.TimeoutExpired:
            servidor.kill()

        print("✓ Cerebro cerrado.")


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

if __name__ == "__main__":

    if not comprobar_archivos():
        input("Presiona ENTER para salir...")
        sys.exit(1)

    if not iniciar_cerebro():
        input("Presiona ENTER para salir...")
        sys.exit(1)

    print("=" * 60)
    print("       ASISTENTE LISTO")
    print("=" * 60)
    print()
    print("Hablaré contigo mediante el micrófono.")
    print("Para salir presiona Ctrl+C.")
    print()

    try:

        while True:

            texto = escuchar()

            if texto is None:
                continue

            respuesta = preguntar_cerebro(texto)

            if respuesta is None:
                continue

            print()
            print("🤖 Asistente:")
            print(respuesta)

            hablar(respuesta)

            print()
            print("-" * 60)
            print()

    except KeyboardInterrupt:

        print()
        print("Interrupción recibida.")

    finally:

        detener_cerebro()