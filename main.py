import os
import re
import sys
import unicodedata
import time
import json
import random
import queue
import threading
import subprocess
import urllib.request

import psutil
import numpy as np
import sounddevice as sd
import soundfile as sf
import webview


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------- CEREBRO ----------

CEREBRO_MODELO = os.path.join(
    BASE_DIR,
    "Modelos",
    "Cerebro 4B (llama.cpp)",
    "Qwen3-4B-Q4_K_M.gguf"
)

LLAMA_SERVER = os.path.join(
    BASE_DIR,
    "Motores",
    "Cerebro",
    "llama-b10588-bin-win-cpu-x64",
    "llama-server.exe"
)


# ---------- WHISPER ----------

# Si cambias de modelo (por ejemplo a ggml-large-v3-turbo-q5_0.bin
# o ggml-medium-q5_0.bin), solo cambia el nombre del archivo aquí.
WHISPER_MODELO = os.path.join(
    BASE_DIR,
    "Modelos",
    "Oidos (Whisper Base)",
    "ggml-base.bin"
)

WHISPER_EXE = os.path.join(
    BASE_DIR,
    "Motores",
    "Oidos",
    "whisper-bin-x64",
    "Release",
    "whisper-cli.exe"
)

# Ajustes específicos de Whisper
WHISPER_HILOS = max(
    2,
    psutil.cpu_count(logical=False) or 2
)

# Búsqueda más amplia = transcripción más precisa
WHISPER_BEST_OF = 5
WHISPER_BEAM_SIZE = 5
WHISPER_NO_SPEECH_THOLD = 0.60

# Contexto para que Whisper reconozca mejor tu vocabulario
WHISPER_PROMPT = (
    "Conversación en español con Oddye, un asistente de voz. "
    "Oddye es su nombre. "
    "Abre Chrome, cierra Word, abre la carpeta Descargas."
)


# ---------- WHISPER: DICTADO EN VIVO (NUEVO) ----------

# Servidor de Whisper: carga el modelo una sola vez y lo deja en
# memoria, así cada frase se transcribe sin recargar "medium".
WHISPER_SERVER_EXE = os.path.join(
    BASE_DIR,
    "Motores",
    "Oidos",
    "whisper-bin-x64",
    "Release",
    "whisper-server.exe"
)

WHISPER_PUERTO = 8081

# Segundos de silencio para cortar una frase (0.8 a 1.0 recomendado).
# Si te corta cuando dudas o te corriges, súbelo a 1.0 o 1.2.
PAUSA_FRASE_SEG = 0.7

# Segundos de silencio (después de hablar) para que el dictado se
# detenga solo. Pon 0 para desactivarlo; entonces se detiene con otro
# clic en el micrófono.
DICTADO_SILENCIO_AUTO_SEG = 2.0

# Precisión del SERVIDOR de Whisper (dictado y comando por voz).
# OJO: WHISPER_BEST_OF / WHISPER_BEAM_SIZE de más arriba solo afectan
# al respaldo con whisper-cli.exe, NO al servidor. Para el servidor
# se cambian estos tres:
#   - Más alto = más preciso pero más lento.
#   - Con el modelo base: 2 ~ 2 s, 3 un poco más, 5 bastante más.
#   - Si se pone lento, baja BEAM y BEST_OF a 2.
WHISPER_SERVER_BEAM = 5
WHISPER_SERVER_BEST_OF = 5
WHISPER_SERVER_NO_SPEECH_THOLD = 0.60


# ---------- MICRÓFONO ----------

# Umbral de voz medido por ventanas de 30 ms.
# Si con voz normal la consola muestra un "RMS máx" menor a este
# valor, bájalo (por ejemplo a 0.004).
UMBRAL_VOZ = 0.01

# None = micrófono predeterminado de Windows.
# Si Python usa el micrófono equivocado, pon aquí el número del
# dispositivo que aparece en sd.query_devices().
MICROFONO_DISPOSITIVO = None


# ---------- PIPER ----------

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


# ---------- ARCHIVOS TEMPORALES ----------

TEMP_DIR = os.path.join(BASE_DIR, "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

GRABACION_WAV = os.path.join(TEMP_DIR, "entrada.wav")
RESPUESTA_WAV = os.path.join(TEMP_DIR, "respuesta.wav")


# ---------- SERVIDOR ----------

LLAMA_URL = "http://127.0.0.1:8080"


# ---------- INTELIGENCIA PATRON ----------

INTELIGENCIA_DIR = os.path.join(BASE_DIR, "InteligenciaPatron")

if INTELIGENCIA_DIR not in sys.path:
    sys.path.insert(0, INTELIGENCIA_DIR)

try:
    from patrones import GestorPatrones
    from observador_pc import ObservadorPC
    from notificaciones import GestorNotificaciones
    from sugerencias import GestorSugerencias

    INTELIGENCIA_DISPONIBLE = True

except Exception as _error_inteligencia:

    print(
        "[InteligenciaPatron] No se pudo importar el módulo: "
        f"{_error_inteligencia}"
    )

    INTELIGENCIA_DISPONIBLE = False


# ---------- ESCLAVO ----------

ESCLAVO_DIR = os.path.join(BASE_DIR, "Esclavo")

if ESCLAVO_DIR not in sys.path:
    sys.path.insert(0, ESCLAVO_DIR)

try:
    import intenciones as esclavo_intenciones
    import acciones_apps as esclavo_apps
    import acciones_carpetas as esclavo_carpetas
    from acciones_sistema import ACCIONES_SISTEMA

    ESCLAVO_DISPONIBLE = True

except Exception as _error_esclavo:

    print(
        "[Esclavo] No se pudo importar el módulo: "
        f"{_error_esclavo}"
    )

    ESCLAVO_DISPONIBLE = False


# ---------- DICTADO EN VIVO (NUEVO) ----------

# dictado.py debe estar en la misma carpeta que main.py.
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from dictado import (
        ServidorWhisper,
        DictadoEnVivo,
        limpiar_autocorrecciones
    )

    DICTADO_DISPONIBLE = True

except Exception as _error_dictado:

    print(
        "[Dictado] No se pudo importar el módulo: "
        f"{_error_dictado}"
    )

    DICTADO_DISPONIBLE = False


# ---------- CHATS GUARDADOS (NUEVO) ----------

# chats.py debe estar en la misma carpeta que main.py.
# Cada conversación se guarda como un .json dentro de Chats/.
CHATS_DIR = os.path.join(BASE_DIR, "Chats")

try:
    from chats import GestorChats

    CHATS_DISPONIBLE = True

except Exception as _error_chats:

    print(
        "[Chats] No se pudo importar chats.py: "
        f"{_error_chats}"
    )

    CHATS_DISPONIBLE = False

# Cuántos caracteres de historial se le devuelven a Qwen al reabrir
# un chat (para no pasarse del contexto del modelo).
CHATS_MAX_CARACTERES_CONTEXTO = 7000


# ---------- CARPETA CONFIG: AJUSTES Y RECURSOS (NUEVO) ----------

# Todo lo de optimización y gestión de recursos vive en Config/:
#   Config/ajustes.py              -> los números que se cambian
#   Config/recursos.py             -> memoria, GPU y procesos viejos
#   Config/diagnostico_memoria.py  -> informe de quién gasta la RAM
CONFIG_DIR = os.path.join(BASE_DIR, "Config")

if CONFIG_DIR not in sys.path:
    sys.path.insert(0, CONFIG_DIR)

try:
    import recursos

    RECURSOS_DISPONIBLE = True

except Exception as _error_recursos:

    print(
        "[Memoria] No se pudo importar recursos.py: "
        f"{_error_recursos}"
    )

    RECURSOS_DISPONIBLE = False

# Valores de respaldo: los que mandan están en Config/ajustes.py.
# Máximo de la RAM total que puede usar Oddye (todo junto: cerebro,
# oídos, voz y ventana). Si se pasa, libera memoria.
RAM_MAXIMA_PORCENTAJE = 40

# Si hay una GPU DEDICADA y tu llama-server trae soporte (CUDA/Vulkan),
# máximo de su memoria que se usa para el cerebro.
# Las GPU integradas (Intel Iris/UHD) comparten la RAM: no se usan.
GPU_MAXIMA_PORCENTAJE = 60

# Modo ahorro extremo: usa un modelo más pequeño si lo tienes en la
# carpeta (por ejemplo Qwen3-1.7B-Q4_K_M.gguf, ~1.1 GB). Con él, toda
# la IA cabe en unos 2.5-3 GB. Pon True para activarlo.
MODO_AHORRO_EXTREMO = False
NOMBRE_MODELO_LIGERO = "Qwen3-1.7B-Q4_K_M.gguf"

# Cada cuántos segundos mide el consumo de memoria.
MEMORIA_INTERVALO_SEG = 15

# Registro del consumo (para ver qué proceso gasta más). None = no guardar.
MEMORIA_LOG = os.path.join(BASE_DIR, "Config", "memoria_log.txt")


# ---------- ESCUCHA POR NOMBRE, TIPO ALEXA (NUEVO) ----------

# escucha.py debe estar en la misma carpeta que main.py.
# Deja el micrófono atento y se activa cuando dices "Oddye".
try:
    from escucha import EscuchaNombre

    ESCUCHA_DISPONIBLE = True

except Exception as _error_escucha:

    print(
        "[Escucha] No se pudo importar escucha.py: "
        f"{_error_escucha}"
    )

    ESCUCHA_DISPONIBLE = False

# True = al abrir Oddye ya queda escuchando su nombre.
ESCUCHA_AL_INICIAR = True

# Si dices solo "Oddye", cuántos segundos espera tu orden.
ESCUCHA_ESPERA_ORDEN_SEG = 7.0

# Segundos de silencio para dar por terminada una frase.
ESCUCHA_SILENCIO_FIN_SEG = 0.7

# True = cuando la llamas por voz, responde en voz alta aunque el
# botón del altavoz esté apagado.
ESCUCHA_RESPONDER_EN_VOZ = True

# Archivo donde la escucha anota lo que oyó (hora, duración, texto y
# si lo tomó como nombre, lo ignoró, etc.). Sirve para afinar.
# Pon None para no guardar nada.
ESCUCHA_LOG = os.path.join(BASE_DIR, "escucha_log.txt")

# Sube este valor si se activa con ruido o con otras personas
# hablando lejos; bájalo si no te oye (rango útil: 0.006 - 0.03).
ESCUCHA_UMBRAL_MINIMO = 0.012


# ---------- VOZ: MOTOR PIPER EN MEMORIA (NUEVO) ----------

# voz.py debe estar en la misma carpeta que main.py.
try:
    from voz import MotorVoz, PIPER_DISPONIBLE

    MOTOR_VOZ_DISPONIBLE = PIPER_DISPONIBLE

except Exception as _error_voz:

    print(
        "[Voz] No se pudo importar voz.py: "
        f"{_error_voz}"
    )

    MOTOR_VOZ_DISPONIBLE = False

# Velocidad: menor = más rápida (1.0 = la velocidad original del
# modelo, antes estaba en 1.08 que es MÁS LENTA). Rango útil: 0.85-1.0
VOZ_VELOCIDAD = 0.93

# Expresividad: más alto = menos monótona (0.6 plana, 0.8 muy viva).
VOZ_VARIACION = 0.72

# Ritmo: más alto = duración de sílabas más irregular, más humana.
VOZ_RITMO = 0.90

# Pausa entre frases, en segundos (antes había ~0.7 s).
VOZ_PAUSA_FRASE = 0.16

# True = empieza a hablar mientras Qwen todavía escribe la respuesta.
VOZ_STREAMING = True

# True = el texto aparece en la ventana al mismo tiempo que Oddye lo
# dice, palabra por palabra, en vez de salir todo al final.
# (Solo aplica cuando Oddye responde en voz.)
TEXTO_AL_UNISONO = True

# True = sin voz, el texto también se va escribiendo mientras Qwen
# lo genera (en vez de salir todo al final).
TEXTO_EN_VIVO = True

# En modo voz las respuestas son más cortas (se oyen, no se leen).
MAX_TOKENS_VOZ = 200

PROMPT_VOZ = (
    "Estás hablando en voz alta, no escribiendo. Habla como una "
    "persona en una conversación natural: frases cortas, directas "
    "y cálidas. Empieza respondiendo de inmediato. Nada de listas, "
    "viñetas, asteriscos, emojis, títulos ni símbolos; si hay "
    "varios pasos, enlázalos con palabras como \"primero\", "
    "\"luego\" y \"al final\". Puedes usar alguna expresión "
    "natural como \"claro\" o \"a ver\", pero sin exagerar. "
    "Máximo tres o cuatro frases, salvo que te pidan más."
)


SEGUNDOS_GRABACION_COMANDO = 4


# ============================================================
# PROMPTS
# ============================================================

PROMPT_SISTEMA = (
    "Te llamas Oddye. Eres un asistente de inteligencia artificial "
    "que corre completamente offline en la computadora del usuario, "
    "sin conexión a internet. Tu propósito es ayudar con tareas "
    "universitarias y de oficina: redacción, organización, dudas "
    "académicas, documentos y trabajo del día a día. "
    "Si te preguntan tu nombre, quién eres o qué eres, respondes "
    "que te llamas Oddye. "
    "Tu tono es formal, claro y profesional, pero cercano y "
    "servicial, no frío ni robótico. Vas directo a resolver el "
    "problema del usuario. "
    "Respondes siempre en español, de forma breve y directa, sin "
    "relleno innecesario. "
    "Eres capaz de abrir y cerrar aplicaciones, aunque a veces se "
    "te dificulta un poco."
)

PROMPT_SISTEMA_PENSANDO = (
    "Te llamas Oddye. Eres un asistente de inteligencia artificial "
    "que corre completamente offline en la computadora del usuario. "
    "Tu propósito es ayudar con tareas universitarias y de oficina. "
    "Si te preguntan tu nombre, quién eres o qué eres, respondes "
    "que te llamas Oddye. "
    "Piensa el problema con cuidado, paso a paso, antes de "
    "responder. Luego entrega una respuesta clara, formal y bien "
    "organizada en español."
)


# ============================================================
# AJUSTES DEL CEREBRO
# ============================================================

CTX_SIZE = 4096

# Presupuesto de tokens por tipo de petición. Oddye ya NO adivina:
# antes de responder se le dice cuántas palabras le caben, y la
# respuesta se planifica para terminar completa dentro de ese límite.
#   - Preguntas normales: cortas y directas.
#   - Cosas largas (cuento, redacción, resumen, código...): más espacio.
# Más tokens = respuestas más completas pero más lentas.
MAX_TOKENS_RESPUESTA = 320
MAX_TOKENS_LARGO = 700
MAX_TOKENS_VOZ_LARGO = 450
MAX_TOKENS_PENSANDO = 800

# Para que no repita palabras ni frases (1.0 = sin penalización).
REPETICION_PENALIZACION = 1.12
MAX_TURNOS_HISTORIAL = 10
MINUTOS_INACTIVIDAD = 5


# ============================================================
# AJUSTES DESDE Config/ajustes.py
# ============================================================
#
# Todo lo que escribas en Config/ajustes.py reemplaza a los valores de
# arriba. Así los números de rendimiento están en un solo lugar.
#

REGISTRO_MEMORIA = True
REGISTRO_ESCUCHA = True

try:

    import ajustes as _ajustes

    for _nombre in dir(_ajustes):

        if _nombre.isupper():
            globals()[_nombre] = getattr(_ajustes, _nombre)

except ImportError:

    print(
        "[Config] No encontré Config/ajustes.py; uso los valores "
        "de respaldo de main.py."
    )

except Exception as _error_ajustes:

    print(f"[Config] Error leyendo Config/ajustes.py: {_error_ajustes}")

CEREBRO_MODELO_LIGERO = os.path.join(
    BASE_DIR,
    "Modelos",
    "Cerebro 4B (llama.cpp)",
    NOMBRE_MODELO_LIGERO
)

if not REGISTRO_MEMORIA:
    MEMORIA_LOG = None

if not REGISTRO_ESCUCHA:
    ESCUCHA_LOG = None


# ============================================================
# AJUSTES DE SUGERENCIAS
# ============================================================

INTERVALO_REVISION_SUGERENCIAS = 20

SUGERENCIAS_GENERALES = [
    "¿Necesitas ayuda con algo?",
    "¿Hay algo que pueda hacer por ti?",
    "¿Qué planes tienes para hoy?",
    "¿Quieres que te ayude a organizar algo?",
    "¿Quieres revisar algo de tu PC?",
    "¿Necesitas ayuda con alguna tarea?",
    "¿Quieres que hagamos algo juntos?",
    "¿Hay algo que hayas estado intentando hacer y no hayas podido?",
    "¿Quieres que te ayude a organizar tus pendientes?",
    "¿Quieres preguntarme algo?",
]


# ============================================================
# DETECCIÓN DE HARDWARE
# ============================================================

def detectar_hilos():

    nucleos_fisicos = psutil.cpu_count(logical=False) or 2

    return max(2, nucleos_fisicos)


# ============================================================
# API DEL ASISTENTE
# ============================================================

# ============================================================
# PRESUPUESTO DE RESPUESTA (para que no salga cortada)
# ============================================================

_RE_PETICION_LARGA = re.compile(
    r"\b(cuento|historia|relato|fabula|leyenda|ensayo|redacta|"
    r"redaccion|carta|resumen|resume|resumeme|poema|discurso|"
    r"articulo|informe|parrafos?|detall\w*|paso a paso|codigo|"
    r"programa|script|guion|cancion|monologo|dialogo|composicion|"
    r"presentacion|lista de|ejemplos|explicame|cuentame|"
    r"largo|extenso|completo)\b"
)

# Un token de Qwen en español ~ 2.8 caracteres (estimación prudente).
_CHARS_POR_TOKEN = 2.8


def _sin_tildes(texto):

    texto = unicodedata.normalize("NFD", (texto or "").lower())

    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _estimar_tokens(mensajes):

    chars = sum(len(m.get("content", "")) + 12 for m in mensajes)

    return int(chars / _CHARS_POR_TOKEN) + 16


def calcular_presupuesto(texto, mensajes, voz, pensando):
    """
    Devuelve (max_tokens, palabras, es_largo).

    max_tokens se ajusta a lo que REALMENTE queda libre en el contexto
    después del prompt y del historial; si no cabe, se descartan los
    mensajes más viejos del historial.
    """

    es_largo = bool(_RE_PETICION_LARGA.search(_sin_tildes(texto)))

    if pensando:
        base = MAX_TOKENS_PENSANDO
    elif voz:
        base = MAX_TOKENS_VOZ_LARGO if es_largo else MAX_TOKENS_VOZ
    else:
        base = MAX_TOKENS_LARGO if es_largo else MAX_TOKENS_RESPUESTA

    margen = 96

    # Lo mínimo que queremos tener libre antes de descartar historial.
    deseado = min(base, 400)

    # mensajes[0] = sistema, mensajes[-1] = lo último que dijo el usuario.
    while (
        len(mensajes) > 2
        and CTX_SIZE - _estimar_tokens(mensajes) - margen < deseado
    ):
        del mensajes[1]

    libre = CTX_SIZE - _estimar_tokens(mensajes) - margen

    max_tokens = max(96, min(base, libre))

    # ~0.5 palabras por token deja margen para cerrar bien.
    palabras = max(30, int(max_tokens * 0.5))

    return max_tokens, palabras, es_largo


def nota_de_limite(palabras, es_largo, voz):

    nota = (
        f"LÍMITE DE ESTA RESPUESTA: máximo {palabras} palabras. "
        "Ve directo al punto: la primera frase ya contesta lo que "
        "pidieron. Sin saludo, sin repetir la pregunta, sin "
        "muletillas de cortesía, sin despedida ni ofrecer más ayuda. "
        "No repitas palabras ni ideas. "
    )

    if es_largo:

        nota += (
            "Si es un texto creativo o largo (cuento, redacción, "
            "resumen, etc.), planifícalo antes de escribir para que "
            "tenga inicio, desarrollo y un final completo DENTRO del "
            "límite; si el tema no cabe, hazlo más corto y condensado, "
            "pero nunca lo dejes a medias."
        )

    else:

        nota += (
            "Sé breve: lo normal son entre una y cuatro frases."
            if not voz else
            "Sé breve: lo normal son dos o tres frases."
        )

    return nota


class RespuestaCancelada(Exception):
    pass


def recortar_a_oracion(texto, minimo=0.4):
    """Si la respuesta se cortó, la deja en la última oración completa."""

    texto = (texto or "").rstrip()

    if not texto:
        return texto

    if re.search(r"[.!?…][\"'”»)\]]*$", texto):
        return texto

    cortes = list(re.finditer(r"[.!?…][\"'”»)\]]*(?=\s|$)", texto))

    if cortes and cortes[-1].end() >= len(texto) * minimo:
        return texto[:cortes[-1].end()].rstrip()

    return texto.rstrip(" ,;:") + "…"


class Api:

    def __init__(self):

        # ---------- CEREBRO ----------

        self.servidor = None
        self.cerebro_listo = False

        # ---------- CONVERSACIÓN ----------

        self.historial = []

        # ---------- CHATS GUARDADOS (NUEVO) ----------
        # Con guion bajo para que pywebview no los recorra como API.

        self._chats = None
        self._chat_id = None
        self._lock_chats = threading.Lock()

        if CHATS_DISPONIBLE:

            try:

                self._chats = GestorChats(CHATS_DIR)

            except Exception as error:

                print(
                    "[Chats] No se pudo iniciar el guardado de "
                    f"chats: {error}"
                )

                self._chats = None

        # ---------- ACTIVIDAD ----------

        self.ultima_actividad = time.time()

        # ---------- CONTROL ----------

        self._lock = threading.Lock()
        self._cerrando = False
        self._vigilante_activo = False

        # ---------- MODOS ----------

        self.modo_pensamiento = False
        self.modo_voz = False

        # ---------- ESTADO DE VOZ ----------

        self._voz_hablando = False

        # Texto al unísono con la voz (NUEVO). Con guion bajo para que
        # pywebview no lo recorra como API.
        self._ui_cola = queue.Queue()
        self._ui_turno = None
        self._ui_hilo = None
        self._ui_contador_turnos = 0
        self._ui_dicho = []

        # Control de memoria (NUEVO).
        self._vigilante_memoria = None
        self._plan_cerebro = None

        # Cancelar la respuesta en curso (botón de detener).
        self._cancelado = threading.Event()
        self._conexion_llm = None

        # Motor de voz con Piper cargado una sola vez (NUEVO).
        # Si algo falla, _hablar() usa el método anterior (python -m piper).
        self._motor_voz = None

        if (
            MOTOR_VOZ_DISPONIBLE
            and os.path.isfile(PIPER_MODELO)
            and os.path.isfile(PIPER_CONFIG)
        ):

            try:

                _ajustes_voz = dict(
                    modelo=PIPER_MODELO,
                    config=PIPER_CONFIG,
                    length_scale=VOZ_VELOCIDAD,
                    noise_scale=VOZ_VARIACION,
                    noise_w=VOZ_RITMO,
                    pausa_frase=VOZ_PAUSA_FRASE,
                    al_evento=self._evento_motor_voz
                )

                try:

                    self._motor_voz = MotorVoz(
                        al_frase=self._frase_hablada,
                        **_ajustes_voz
                    )

                except TypeError:

                    # voz.py viejo, sin texto al unísono.
                    print(
                        "[Voz] Este voz.py no admite texto al unísono; "
                        "actualízalo."
                    )

                    self._motor_voz = MotorVoz(**_ajustes_voz)

            except Exception as error:

                print(
                    "[Voz] Error creando el motor de voz: "
                    f"{error}"
                )

                self._motor_voz = None

        # ---------- AUDIO ----------

        self._audio_stream = None
        self._buffer_audio = []

        # ---------- VENTANA ----------

        self._ventana = None

        # ---------- INTELIGENCIA PATRON ----------

        self.patrones = None
        self.observador = None
        self.notificaciones = None
        self.sugerencias = None

        self._hilo_sugerencias_activo = False

        if INTELIGENCIA_DISPONIBLE:

            try:

                self.patrones = GestorPatrones()

                self.observador = ObservadorPC(
                    self.patrones
                )

                self.notificaciones = GestorNotificaciones()

                self.sugerencias = GestorSugerencias(
                    gestor_notificaciones=self.notificaciones
                )

                print(
                    "[InteligenciaPatron] Sistema de patrones "
                    "y sugerencias listo."
                )

            except Exception as error:

                print(
                    "[InteligenciaPatron] Error iniciando el "
                    f"sistema: {error}"
                )

                self.patrones = None
                self.observador = None
                self.notificaciones = None
                self.sugerencias = None

        # ---------- DICTADO EN VIVO (NUEVO) ----------
        # Con guion bajo para que pywebview no los recorra como API.

        self._whisper_servidor = None
        self._dictado = None

        if DICTADO_DISPONIBLE:

            try:

                self._whisper_servidor = ServidorWhisper(
                    exe=WHISPER_SERVER_EXE,
                    modelo=WHISPER_MODELO,
                    hilos=WHISPER_HILOS,
                    prompt=WHISPER_PROMPT,
                    puerto=WHISPER_PUERTO,
                    beam_size=WHISPER_SERVER_BEAM,
                    best_of=WHISPER_SERVER_BEST_OF,
                    no_speech_thold=WHISPER_SERVER_NO_SPEECH_THOLD
                )

                self._dictado = DictadoEnVivo(
                    servidor=self._whisper_servidor,
                    al_texto=self._empujar_dictado,
                    umbral_voz=UMBRAL_VOZ,
                    pausa_seg=PAUSA_FRASE_SEG,
                    dispositivo=MICROFONO_DISPOSITIVO,
                    silencio_auto_seg=DICTADO_SILENCIO_AUTO_SEG,
                    al_silencio=self._dictado_silencio,
                    al_terminar=self._dictado_terminado
                )

                print("[Dictado] Dictado en vivo listo.")

            except Exception as error:

                print(
                    "[Dictado] Error iniciando el dictado: "
                    f"{error}"
                )

                self._whisper_servidor = None
                self._dictado = None


        # ---------- ESCUCHA POR NOMBRE (NUEVO) ----------

        self._escucha = None

        if ESCUCHA_DISPONIBLE and self._whisper_servidor is not None:

            try:

                self._escucha = EscuchaNombre(
                    transcribir=self._escucha_transcribir,
                    al_nombre=self._escucha_al_nombre,
                    al_comando=self._escucha_al_comando,
                    pausado=self._escucha_pausada,
                    al_estado=self._escucha_estado,
                    dispositivo=MICROFONO_DISPOSITIVO,
                    umbral_minimo=ESCUCHA_UMBRAL_MINIMO,
                    silencio_fin_seg=ESCUCHA_SILENCIO_FIN_SEG,
                    espera_comando_seg=ESCUCHA_ESPERA_ORDEN_SEG,
                    log_ruta=ESCUCHA_LOG,
                    ignorar=[WHISPER_PROMPT] + [
                        frase.strip()
                        for frase in WHISPER_PROMPT.split(".")
                        if frase.strip()
                    ]
                )

            except Exception as error:

                print(f"[Escucha] No se pudo preparar: {error}")

                self._escucha = None


    # ========================================================
    # VENTANA
    # ========================================================

    def set_ventana(self, window):

        self._ventana = window

        # Carga Piper en segundo plano (una sola vez).
        if self._motor_voz is not None:
            self._motor_voz.iniciar()

        # Cierra servidores de Whisper que hayan quedado vivos de una
        # sesión anterior (cada uno ocupa memoria).
        if RECURSOS_DISPONIBLE and self._whisper_servidor is not None:

            try:

                cerrados = recursos.limpiar_huerfanos([WHISPER_SERVER_EXE])

                if cerrados:
                    print(
                        f"[Memoria] Cerré {cerrados} servidor(es) de "
                        "Whisper viejo(s)."
                    )

            except Exception:
                pass

        # Empieza a cargar Whisper en segundo plano mientras
        # se abre la interfaz.
        if self._whisper_servidor is not None:

            try:
                self._whisper_servidor.iniciar()
            except Exception as error:
                print(
                    "[Dictado] No se pudo iniciar el servidor "
                    f"de Whisper: {error}"
                )

        if self._escucha is not None and ESCUCHA_AL_INICIAR:

            threading.Thread(
                target=self._arrancar_escucha,
                daemon=True
            ).start()


    def _enfocar_ventana(self):

        if self._ventana is None:
            return

        try:
            self._ventana.restore()
        except Exception:
            pass

        try:
            self._ventana.show()
        except Exception:
            pass


    def _empujar_mensaje_chat(self, texto, tipo):

        if self._ventana is None or not texto:
            return

        try:

            self._ventana.evaluate_js(
                "mostrarMensajeExterno("
                + json.dumps(texto)
                + ", "
                + json.dumps(tipo)
                + ")"
            )

        except Exception as error:

            print(
                "[InteligenciaPatron] No se pudo escribir "
                f"en el chat: {error}"
            )


    def _actualizar_estado_externo(self, texto, pensando):

        if self._ventana is None:
            return

        try:

            self._ventana.evaluate_js(
                "setEstadoExterno("
                + json.dumps(texto)
                + ", "
                + ("true" if pensando else "false")
                + ")"
            )

        except Exception:
            pass


    # ========================================================
    # ARRANQUE DEL CEREBRO
    # ========================================================

    def _encender(self):

        if self._cerrando:

            return {
                "ok": False,
                "mensaje": "El asistente se está cerrando."
            }

        if self.servidor is not None and self.cerebro_listo:

            return {
                "ok": True
            }

        if not os.path.isfile(LLAMA_SERVER):

            return {
                "ok": False,
                "mensaje": (
                    "No encontré llama-server.exe en:\n"
                    f"{LLAMA_SERVER}"
                )
            }

        if not os.path.isfile(CEREBRO_MODELO):

            return {
                "ok": False,
                "mensaje": (
                    "No encontré el modelo en:\n"
                    f"{CEREBRO_MODELO}"
                )
            }

        # ----------------------------------------------------
        # Plan de memoria según tu equipo (NUEVO)
        # ----------------------------------------------------

        modelo = CEREBRO_MODELO

        if MODO_AHORRO_EXTREMO and os.path.isfile(CEREBRO_MODELO_LIGERO):
            modelo = CEREBRO_MODELO_LIGERO
            print("[Memoria] Modo ahorro: usando el modelo ligero.")

        global CTX_SIZE

        plan = None

        if RECURSOS_DISPONIBLE:

            try:

                # Cierra servidores que hayan quedado vivos de antes.
                cerrados = recursos.limpiar_huerfanos(
                    [LLAMA_SERVER, WHISPER_SERVER_EXE]
                    if self._whisper_servidor is None
                    else [LLAMA_SERVER]
                )

                if cerrados:
                    print(
                        f"[Memoria] Cerré {cerrados} cerebro(s) viejo(s) "
                        "que seguían abiertos."
                    )

                plan = recursos.planificar_cerebro(
                    modelo,
                    LLAMA_SERVER,
                    ctx_deseado=CTX_SIZE,
                    ram_pct=RAM_MAXIMA_PORCENTAJE,
                    gpu_pct=GPU_MAXIMA_PORCENTAJE
                )

                self._plan_cerebro = plan

                for nota in plan["notas"]:
                    print(f"[Memoria] {nota}")

                print(
                    f"[Memoria] Límite: {plan['presupuesto_mb'] / 1024:.1f}"
                    f" GB de {plan['ram_total_mb'] / 1024:.1f} GB | "
                    f"Estimado del cerebro: "
                    f"{plan['estimado_mb'] / 1024:.1f} GB"
                )

            except Exception as error:

                print(f"[Memoria] No se pudo planificar: {error}")

                plan = None

        if plan is not None:

            CTX_SIZE = plan["ctx"]

            intentos = recursos.comandos_llama(
                LLAMA_SERVER,
                modelo,
                plan,
                detectar_hilos()
            )

        else:

            intentos = [[
                LLAMA_SERVER,
                "-m",
                modelo,
                "--port",
                "8080",
                "--ctx-size",
                str(CTX_SIZE),
                "--cache-type-k",
                "q4_0",
                "--cache-type-v",
                "q4_0",
                "--threads",
                str(detectar_hilos()),
            ]]


        # ----------------------------------------------------
        # Arranque: se prueba la versión optimizada y, si esta
        # versión de llama-server no entiende algún parámetro y se
        # cierra, se pasa a la siguiente más sencilla.
        # ----------------------------------------------------

        for numero, comando in enumerate(intentos, start=1):

            try:

                self.servidor = subprocess.Popen(
                    comando,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )

            except Exception as e:

                self.servidor = None

                return {
                    "ok": False,
                    "mensaje": f"No se pudo iniciar llama-server: {e}"
                }

            murio = False

            for _ in range(30):

                if self._cerrando:

                    self._apagar()

                    return {
                        "ok": False,
                        "mensaje": "El asistente se está cerrando."
                    }

                if self.servidor.poll() is not None:

                    murio = True

                    break

                try:

                    r = urllib.request.urlopen(
                        LLAMA_URL + "/health",
                        timeout=1
                    )

                    if r.status == 200:

                        self.cerebro_listo = True

                        self._iniciar_vigilante_memoria()

                        if numero > 1:
                            print(
                                f"[Memoria] Arrancó con la opción "
                                f"{numero} (más sencilla)."
                            )

                        return {
                            "ok": True
                        }

                except Exception:
                    pass

                time.sleep(1)

            if murio and numero < len(intentos):

                print(
                    "[Memoria] llama-server no aceptó los parámetros "
                    "optimizados; pruebo con unos más sencillos."
                )

                self.servidor = None

                continue

            if murio:

                self.servidor = None
                self.cerebro_listo = False

                return {
                    "ok": False,
                    "mensaje": "llama-server se cerró inesperadamente."
                }

            break

        self._apagar()

        return {
            "ok": False,
            "mensaje": "El cerebro no respondió a tiempo."
        }


    # ========================================================
    # APAGADO DEL CEREBRO
    # ========================================================

    def _iniciar_vigilante_memoria(self):

        if not RECURSOS_DISPONIBLE or self._vigilante_memoria is not None:
            return

        try:

            total = recursos.ram_total_mb()

            self._vigilante_memoria = recursos.VigilanteMemoria(
                presupuesto_mb=int(total * RAM_MAXIMA_PORCENTAJE / 100),
                ocupada=self._memoria_ocupada,
                liberar_cerebro=recursos.borrar_cache_llama,
                intervalo=MEMORIA_INTERVALO_SEG,
                log_ruta=MEMORIA_LOG
            )

            self._vigilante_memoria.iniciar()

        except Exception as error:

            print(f"[Memoria] No se pudo iniciar el vigilante: {error}")

            self._vigilante_memoria = None


    def _memoria_ocupada(self):

        # Oddye está pensando, hablando o escuchando una orden.
        escucha = self._escucha

        return bool(
            self._voz_hablando
            or self._audio_stream is not None
            or self._ui_turno is not None
            or (escucha is not None and escucha._ocupada)
        )


    def estado_memoria(self):

        if self._vigilante_memoria is None:

            return {
                "ok": False,
                "mensaje": "El control de memoria no está activo."
            }

        medida = self._vigilante_memoria.medir()

        return {
            "ok": True,
            **medida
        }


    def _apagar(self):

        self.cerebro_listo = False

        proceso = self.servidor
        self.servidor = None

        if proceso is not None:

            try:

                if proceso.poll() is None:

                    proceso.terminate()

                    try:

                        proceso.wait(timeout=5)

                    except subprocess.TimeoutExpired:

                        proceso.kill()

                        try:
                            proceso.wait(timeout=2)
                        except Exception:
                            pass

            except Exception:
                pass


    # ========================================================
    # CARGAR MODELO
    # ========================================================

    def cargar_modelo(self):

        if self._cerrando:

            return {
                "ok": False,
                "mensaje": "El asistente se está cerrando."
            }

        with self._lock:

            resultado = self._encender()

        if resultado["ok"]:

            self._iniciar_vigilante_inactividad()
            self._iniciar_hilo_sugerencias()

        return resultado


    # ========================================================
    # CERRAR ASISTENTE
    # ========================================================

    def apagar_cerebro(self):

        if self._cerrando:
            return

        self._cerrando = True

        try:

            if self._audio_stream is not None:

                self._audio_stream.stop()
                self._audio_stream.close()
                self._audio_stream = None

        except Exception:
            pass

        # Escucha por nombre (NUEVO)
        try:

            if self._escucha is not None:
                self._escucha.detener()

        except Exception:
            pass

        try:

            if self._vigilante_memoria is not None:
                self._vigilante_memoria.detener()

        except Exception:
            pass

        # Dictado en vivo y servidor de Whisper (NUEVO)
        try:

            if self._dictado is not None:
                self._dictado.detener()

            if self._whisper_servidor is not None:
                self._whisper_servidor.detener()

        except Exception:
            pass

        try:

            if self._motor_voz is not None:
                self._motor_voz.cerrar()

        except Exception:
            pass

        try:
            sd.stop()
        except Exception:
            pass

        with self._lock:
            self._apagar()


    # ========================================================
    # VIGILANTE DE INACTIVIDAD
    # ========================================================

    def _iniciar_vigilante_inactividad(self):

        if self._vigilante_activo:
            return

        self._vigilante_activo = True

        hilo = threading.Thread(
            target=self._vigilar_inactividad,
            daemon=True
        )

        hilo.start()


    def _vigilar_inactividad(self):

        try:

            while not self._cerrando:

                time.sleep(30)

                with self._lock:

                    if not self.cerebro_listo:
                        return

                    inactivo_por = (
                        time.time() - self.ultima_actividad
                    )

                    if inactivo_por > MINUTOS_INACTIVIDAD * 60:

                        self._apagar()

                        return

        finally:

            self._vigilante_activo = False


    # ========================================================
    # MODOS
    # ========================================================

    def alternar_pensamiento(self):

        self.modo_pensamiento = not self.modo_pensamiento

        return {
            "activo": self.modo_pensamiento
        }


    def cancelar_respuesta(self):
        """Detiene lo que Oddye esté generando o diciendo ahora mismo."""

        self._cancelado.set()

        motor = self._motor_voz

        if motor is not None:

            try:
                motor.detener()
            except Exception:
                pass

            # Avisa a la ventana que ya no está hablando.
            self._voz_hablando = False
            self._notificar_voz("terminado")

        if self._ui_turno is not None:
            self._ui_cola.put(("cancelar_ui", None, None))

        return {"ok": True}


    def alternar_voz(self):

        self.modo_voz = not self.modo_voz

        return {
            "activo": self.modo_voz
        }


    # ========================================================
    # CHAT
    # ========================================================

    def enviar_mensaje(self, texto):

        texto = (texto or "").strip()

        if not texto:

            return {
                "ok": False,
                "respuesta": "Escribe algo primero."
            }


        # ----------------------------------------------------
        # Actividad
        # ----------------------------------------------------

        with self._lock:

            if self._cerrando:

                return {
                    "ok": False,
                    "respuesta": "El asistente se está cerrando."
                }

            self.ultima_actividad = time.time()

            if not self.cerebro_listo:

                resultado = self._encender()

                if not resultado["ok"]:

                    return {
                        "ok": False,
                        "respuesta": resultado.get(
                            "mensaje",
                            "No se pudo encender el cerebro."
                        )
                    }

                self._iniciar_vigilante_inactividad()
                self._iniciar_hilo_sugerencias()


        # ----------------------------------------------------
        # Historial
        # ----------------------------------------------------

        self.historial.append({
            "role": "user",
            "content": texto
        })

        self.historial = self.historial[
            -MAX_TURNOS_HISTORIAL * 2:
        ]


        # ----------------------------------------------------
        # Modo pensamiento
        # ----------------------------------------------------

        usar_pensamiento = self.modo_pensamiento

        if usar_pensamiento:

            prompt_sistema = PROMPT_SISTEMA_PENSANDO

            mensajes = (
                [{"role": "system", "content": prompt_sistema}]
                + self.historial
            )

            max_tokens = MAX_TOKENS_PENSANDO

        else:

            prompt_sistema = PROMPT_SISTEMA

            if self.modo_voz:
                prompt_sistema = prompt_sistema + " " + PROMPT_VOZ

            mensajes = (
                [{"role": "system", "content": prompt_sistema}]
                + self.historial[:-1]
            )

            mensajes.append({
                "role": "user",
                "content": texto + " /no_think"
            })

            max_tokens = MAX_TOKENS_RESPUESTA


        # ----------------------------------------------------
        # Presupuesto: cuántos tokens le caben a la respuesta
        # ----------------------------------------------------
        #
        # Se calcula con lo que queda libre del contexto y se le
        # avisa a Qwen en palabras, para que escriba algo que
        # TERMINE dentro del límite en vez de cortarse a medias.
        #

        max_tokens, palabras, es_largo = calcular_presupuesto(
            texto,
            mensajes,
            self.modo_voz,
            usar_pensamiento
        )

        if not usar_pensamiento:

            # La nota va en el último mensaje (no en el del sistema):
            # así el inicio del prompt es siempre igual y llama-server
            # puede reutilizar lo que ya procesó en vez de repetirlo.
            mensajes[-1] = {
                "role": "user",
                "content": (
                    texto
                    + "\n\n["
                    + nota_de_limite(
                        palabras,
                        es_largo,
                        self.modo_voz
                    )
                    + "] /no_think"
                )
            }

        print(
            f"[Cerebro] Presupuesto: {max_tokens} tokens "
            f"(~{palabras} palabras){' | largo' if es_largo else ''}"
        )


        # El pensamiento se consume en este mensaje.
        self.modo_pensamiento = False


        # ----------------------------------------------------
        # Voz en streaming: Piper habla frase por frase
        # mientras Qwen todavía está escribiendo. (NUEVO)
        # ----------------------------------------------------

        usar_stream = bool(
            self.modo_voz
            and VOZ_STREAMING
            and not usar_pensamiento
            and self._motor_voz is not None
            and self._motor_voz.listo
        )


        # Texto al unísono: la ventana va mostrando cada frase al
        # tiempo que suena.
        sincronizar = bool(
            usar_stream
            and TEXTO_AL_UNISONO
            and self._ventana is not None
        )

        # Sin voz: el texto también se va escribiendo en vivo.
        vivo = bool(
            not sincronizar
            and self._ventana is not None
            and TEXTO_EN_VIVO
        )

        self._cancelado.clear()
        self._ui_dicho = []
        self._parcial_llm = []

        if sincronizar or vivo:

            self._ui_contador_turnos += 1

            self._ui_id_actual = self._ui_contador_turnos

            self._ui_arrancar_hilo()

            self._ui_cola.put((
                "inicio",
                self._ui_id_actual,
                "vivo" if vivo else "voz"
            ))


        # ----------------------------------------------------
        # Petición
        # ----------------------------------------------------

        datos = {
            "messages": mensajes,
            "temperature": 0.6 if usar_pensamiento else 0.7,
            "top_p": 0.95 if usar_pensamiento else 0.8,
            "top_k": 20,
            "repeat_penalty": REPETICION_PENALIZACION,
            "max_tokens": max_tokens,
            "stream": True,
        }

        self._motivo_fin = None

        cuerpo = json.dumps(datos).encode("utf-8")

        solicitud = urllib.request.Request(
            LLAMA_URL + "/v1/chat/completions",
            data=cuerpo,
            headers={
                "Content-Type": "application/json"
            }
        )


        try:

            respuesta = self._abrir_peticion(solicitud)

            texto_respuesta = self._leer_respuesta_en_streaming(
                respuesta,
                con_voz=usar_stream,
                en_vivo=vivo
            )

            if self._cancelado.is_set():
                raise RespuestaCancelada()


            # ------------------------------------------------
            # ¿Se cortó por el límite? Dejarla en una oración
            # completa en vez de a media palabra.
            # ------------------------------------------------

            if self._motivo_fin == "length":

                print(
                    "[Cerebro] La respuesta llegó al límite de "
                    "tokens; se recorta en la última oración."
                )

                texto_respuesta = recortar_a_oracion(texto_respuesta)


            # ------------------------------------------------
            # Guardar respuesta
            # ------------------------------------------------

            self.historial.append({
                "role": "assistant",
                "content": texto_respuesta
            })

            with self._lock:
                self.ultima_actividad = time.time()

            if sincronizar or vivo:
                self._ui_cola.put(("llm", texto_respuesta, None))


            # ------------------------------------------------
            # Voz
            # ------------------------------------------------

            if self.modo_voz and not usar_stream:

                threading.Thread(
                    target=self._hablar,
                    args=(texto_respuesta,),
                    daemon=True
                ).start()


            return {
                "ok": True,
                "respuesta": texto_respuesta,
                "ya_mostrada": bool(sincronizar or vivo)
            }


        except RespuestaCancelada:

            # El usuario la detuvo. Se conserva lo que ya se había
            # dicho (con voz) o escrito (sin voz), en oraciones completas.
            if sincronizar:
                parcial = " ".join(self._ui_dicho).strip()
            else:
                parcial = recortar_a_oracion(
                    "".join(self._parcial_llm).strip(),
                    minimo=0.0
                )

                # Sin ninguna oración completa no se guarda nada.
                if parcial.endswith("…"):
                    parcial = ""

            if sincronizar or vivo:
                self._ui_cola.put(("parcial", None, None))

            if parcial:

                self.historial.append({
                    "role": "assistant",
                    "content": parcial
                })

            elif self.historial and (
                self.historial[-1].get("role") == "user"
            ):

                self.historial.pop()

            print("[Cerebro] Respuesta detenida por el usuario.")

            return {
                "ok": True,
                "respuesta": parcial,
                "ya_mostrada": bool(sincronizar or vivo),
                "cancelada": True
            }


        except Exception as e:

            if sincronizar or vivo:
                self._ui_cola.put(("descartar", None, None))

            if usar_stream and self._motor_voz is not None:
                self._motor_voz.detener()

            if self.historial:

                ultimo = self.historial[-1]

                if (
                    ultimo.get("role") == "user"
                    and ultimo.get("content") == texto
                ):

                    self.historial.pop()


            return {
                "ok": False,
                "respuesta": (
                    f"Error comunicando con el cerebro: {e}"
                )
            }


    # ========================================================
    # TEXTO AL UNÍSONO CON LA VOZ
    # ========================================================
    #
    # Cada frase se muestra en la ventana justo cuando empieza a
    # sonar, repartiendo sus palabras durante lo que dura el audio.
    # Al terminar de hablar, el texto se cambia por la respuesta final
    # completa (la misma que queda guardada en el chat).
    #

    def _ui_arrancar_hilo(self):

        if self._ui_hilo is not None and self._ui_hilo.is_alive():
            return

        self._ui_hilo = threading.Thread(
            target=self._ui_bucle,
            daemon=True
        )

        self._ui_hilo.start()


    def _ui_js(self, codigo):

        if self._ventana is None:
            return

        try:
            self._ventana.evaluate_js(codigo)
        except Exception as error:
            print(f"[Texto] No se pudo actualizar la ventana: {error}")


    def _ui_bucle(self):

        while not self._cerrando:

            try:
                tipo, a, b = self._ui_cola.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                self._ui_procesar(tipo, a, b)
            except Exception as error:
                print(f"[Texto] Error: {error}")


    def _ui_procesar(self, tipo, a, b):

        turno = self._ui_turno

        if tipo == "inicio":

            # Si el turno anterior quedó abierto, se cierra completo.
            if turno is not None:
                self._ui_cerrar(turno)

            self._ui_turno = {
                "id": a,
                "llm": None,
                # Sin voz no hay nada que esperar para cerrar.
                "voz": (b == "vivo")
            }

            return

        if turno is None:
            return

        if tipo == "vivo":

            self._ui_js("agregarTextoVivo(" + json.dumps(a) + ")")

            return

        if tipo == "parcial":

            # Detenida mientras se generaba: queda lo ya mostrado.
            self._ui_js("cancelarMensajeStream()")
            self._ui_turno = None

            return

        if tipo == "cancelar_ui":

            # Detenida cuando ya estaba generada y solo hablaba:
            # se muestra el texto completo de una vez.
            if turno["llm"] is not None:
                self._ui_cerrar(turno)
                self._ui_turno = None

            return

        if tipo == "cerrar":

            # Llegó una petición nueva: si el turno anterior quedó
            # a medias (voz cortada), se deja completo y se cierra.
            if turno["llm"] is not None:
                self._ui_cerrar(turno)
                self._ui_turno = None

            return

        if tipo == "frase":

            self._ui_js(
                "agregarTextoStream("
                + json.dumps(a)
                + ", "
                + json.dumps(round(float(b), 3))
                + ")"
            )

        elif tipo == "llm":

            turno["llm"] = a

            # Por si la voz nunca avisa que terminó.
            threading.Timer(
                90.0,
                lambda: self._ui_cola.put(("forzar", turno["id"], None))
            ).start()

        elif tipo == "voz_fin":

            turno["voz"] = True

        elif tipo == "forzar":

            if a != turno["id"] or turno["llm"] is None:
                return

            turno["voz"] = True

        elif tipo == "descartar":

            self._ui_js("descartarMensajeStream()")
            self._ui_turno = None

            return

        if turno["llm"] is not None and turno["voz"]:

            self._ui_cerrar(turno)

            self._ui_turno = None


    def _ui_cerrar(self, turno):

        self._ui_js(
            "finalizarMensajeStream("
            + json.dumps(turno["llm"] or "")
            + ")"
        )


    def _frase_hablada(self, texto, duracion):

        # Lo llama el motor de voz (en su hilo) al empezar cada frase.
        # Se pasa a otro hilo para no interrumpir el audio.
        if self._ui_turno is not None:

            self._ui_dicho.append(texto)

            self._ui_cola.put(("frase", texto, duracion))


    # ========================================================
    # LECTURA EN STREAMING (voz mientras Qwen escribe)
    # ========================================================

    def _abrir_peticion(self, solicitud):
        """
        Abre la conexión con llama-server sin bloquear: si el usuario
        cancela mientras Qwen todavía procesa el mensaje, se suelta
        de inmediato y la conexión se cierra en cuanto responda.
        """

        resultado = {}

        def _abrir():

            try:
                resultado["resp"] = urllib.request.urlopen(
                    solicitud,
                    timeout=180
                )
            except Exception as error:
                resultado["error"] = error

            # Si ya lo cancelaron, no deja la conexión abierta
            # (así llama-server deja de generar).
            if self._cancelado.is_set() and "resp" in resultado:
                try:
                    resultado["resp"].close()
                except Exception:
                    pass

        hilo = threading.Thread(target=_abrir, daemon=True)
        hilo.start()

        while hilo.is_alive():

            if self._cancelado.is_set():
                raise RespuestaCancelada()

            hilo.join(0.05)

        if "error" in resultado:
            raise resultado["error"]

        return resultado["resp"]


    def _leer_respuesta_en_streaming(
        self,
        respuesta,
        con_voz=True,
        en_vivo=False
    ):

        motor = self._motor_voz if con_voz else None

        if motor is not None:
            motor.comenzar_turno()

        partes = []
        self._parcial_llm = partes

        pendiente = ""
        ultimo_envio = 0.0

        try:

            for linea_bytes in respuesta:

                if self._cancelado.is_set():
                    break

                linea = linea_bytes.decode(
                    "utf-8",
                    errors="ignore"
                ).strip()

                if not linea.startswith("data:"):
                    continue

                carga = linea[5:].strip()

                if carga == "[DONE]":
                    break

                try:
                    dato = json.loads(carga)
                except Exception:
                    continue

                elecciones = dato.get("choices") or []

                if not elecciones:
                    continue

                if elecciones[0].get("finish_reason"):
                    self._motivo_fin = elecciones[0]["finish_reason"]

                fragmento = (
                    (elecciones[0].get("delta") or {})
                    .get("content")
                    or ""
                )

                if fragmento:

                    partes.append(fragmento)

                    if motor is not None:
                        motor.agregar_fragmento(fragmento)

                    if en_vivo:

                        pendiente += fragmento

                        ahora = time.time()

                        if ahora - ultimo_envio >= 0.05 or "\n" in fragmento:

                            self._ui_cola.put(("vivo", pendiente, None))

                            pendiente = ""
                            ultimo_envio = ahora

            if en_vivo and pendiente and not self._cancelado.is_set():
                self._ui_cola.put(("vivo", pendiente, None))

        finally:

            try:
                respuesta.close()
            except Exception:
                pass

            if motor is not None:

                # Si se cortó por el límite, lo que quedó sin terminar
                # (media frase) no se dice en voz alta. Si la detuvo el
                # usuario, no se dice nada más.
                if (
                    self._motivo_fin == "length"
                    or self._cancelado.is_set()
                ):

                    try:

                        with motor._lock:
                            motor._buf = ""

                    except Exception:
                        pass

                if self._cancelado.is_set():
                    motor.detener()
                else:
                    motor.terminar_turno()

        return "".join(partes).strip()


    # ========================================================
    # ESCLAVO — PUNTO DE ENTRADA ÚNICO
    # ========================================================

    def procesar_entrada_usuario(self, texto):

        texto_limpio = (texto or "").strip()

        if self._ui_turno is not None:
            self._ui_cola.put(("cerrar", None, None))

        ultimo_antes = self.historial[-1] if self.historial else None

        resultado = self._procesar_entrada_usuario_interno(texto)

        # Guardar el intercambio en el chat actual (NUEVO).
        try:

            if (
                texto_limpio
                and isinstance(resultado, dict)
                and resultado.get("respuesta")
            ):

                # ¿La respuesta salió de Qwen? Si es así, el
                # historial terminó con un mensaje nuevo del asistente.
                por_qwen = bool(
                    self.historial
                    and self.historial[-1] is not ultimo_antes
                    and self.historial[-1].get("role") == "assistant"
                )

                self._guardar_en_chat(
                    [
                        ("user", texto_limpio),
                        ("assistant", resultado["respuesta"])
                    ],
                    ctx=por_qwen
                )

                resultado["chat_id"] = self._chat_id

        except Exception as error:

            print(f"[Chats] Error guardando el intercambio: {error}")

        return resultado


    def _procesar_entrada_usuario_interno(self, texto):

        texto = (texto or "").strip()

        if not texto:

            return {
                "ok": False,
                "respuesta": "Escribe algo primero."
            }


        # ====================================================
        # ACTIVIDAD
        # ====================================================

        with self._lock:

            if self._cerrando:

                return {
                    "ok": False,
                    "respuesta": "El asistente se está cerrando."
                }

            self.ultima_actividad = time.time()


        # ====================================================
        # ESCLAVO
        # ====================================================

        if ESCLAVO_DISPONIBLE:

            try:

                intencion_app = (
                    esclavo_apps.interpretar_apertura(texto)
                )

            except Exception as error:

                print(
                    "[Esclavo Apps] Error interpretando "
                    f"la aplicación: {error}"
                )

                intencion_app = None


            if (
                intencion_app
                and intencion_app.get("accion") == "abrir_app"
            ):

                nombre = intencion_app.get("nombre")

                resultado = esclavo_apps.abrir_app(
                    nombre,
                    observador=self.observador
                )

                respuesta = resultado.get(
                    "respuesta",
                    resultado.get(
                        "mensaje",
                        "Listo."
                    )
                )

                if self.modo_voz and respuesta:

                    threading.Thread(
                        target=self._hablar,
                        args=(respuesta,),
                        daemon=True
                    ).start()

                return {
                    "ok": resultado.get("ok", False),
                    "respuesta": respuesta
                }


            if (
                intencion_app
                and intencion_app.get("accion") == "cerrar_app"
            ):

                nombre = intencion_app.get("nombre")

                resultado = esclavo_apps.cerrar_app(
                    nombre
                )

                respuesta = resultado.get(
                    "respuesta",
                    resultado.get(
                        "mensaje",
                        "Listo."
                    )
                )

                if self.modo_voz and respuesta:

                    threading.Thread(
                        target=self._hablar,
                        args=(respuesta,),
                        daemon=True
                    ).start()

                return {
                    "ok": resultado.get("ok", False),
                    "respuesta": respuesta
                }


            try:

                intencion = (
                    esclavo_intenciones.detectar_intencion(
                        texto
                    )
                )

            except Exception as error:

                print(
                    "[Esclavo] Error detectando intención:",
                    error
                )

                intencion = {
                    "intencion": "chat"
                }


            tipo = intencion.get("intencion")


            if tipo == "programa":

                resultado = esclavo_apps.abrir_app(
                    intencion["nombre"],
                    observador=self.observador
                )

                respuesta = resultado.get(
                    "respuesta",
                    resultado.get(
                        "mensaje",
                        "Listo."
                    )
                )

                if self.modo_voz and respuesta:

                    threading.Thread(
                        target=self._hablar,
                        args=(respuesta,),
                        daemon=True
                    ).start()

                return {
                    "ok": resultado.get("ok", False),
                    "respuesta": respuesta
                }


            if tipo == "carpeta":

                resultado = esclavo_carpetas.abrir_carpeta(
                    intencion["nombre"]
                )

                respuesta = resultado.get(
                    "respuesta",
                    resultado.get(
                        "mensaje",
                        "Listo."
                    )
                )

                if self.modo_voz and respuesta:

                    threading.Thread(
                        target=self._hablar,
                        args=(respuesta,),
                        daemon=True
                    ).start()

                return {
                    "ok": resultado.get("ok", False),
                    "respuesta": respuesta
                }


            if tipo == "sistema":

                funcion = ACCIONES_SISTEMA.get(
                    intencion.get("accion")
                )

                if funcion is None:

                    return {
                        "ok": False,
                        "respuesta": (
                            "No reconozco ese comando de "
                            "sistema."
                        )
                    }

                resultado = funcion()

                respuesta = resultado.get(
                    "respuesta",
                    resultado.get(
                        "mensaje",
                        "Listo."
                    )
                )

                if self.modo_voz and respuesta:

                    threading.Thread(
                        target=self._hablar,
                        args=(respuesta,),
                        daemon=True
                    ).start()

                return {
                    "ok": resultado.get("ok", False),
                    "respuesta": respuesta
                }


        return self.enviar_mensaje(texto)


    # ========================================================
    # ESCUCHA POR NOMBRE (tipo Alexa)
    # ========================================================

    def _arrancar_escucha(self):

        # Espera a que Whisper esté cargado para no perder la
        # primera vez que la llames.
        for _ in range(240):

            if self._cerrando:
                return

            try:
                if self._whisper_servidor.listo():
                    break
            except Exception:
                pass

            time.sleep(0.5)

        if self._escucha.iniciar():
            self._avisar_escucha(True)


    def _escucha_transcribir(self, audio):

        servidor = self._whisper_servidor

        if servidor is None or not servidor.listo():
            return ""

        return servidor.transcribir(audio) or ""


    def _escucha_pausada(self):

        # Mientras hay otra cosa usando el micrófono o la voz, la
        # escucha por nombre se calla (así no se oye a sí misma).
        if self._voz_hablando or self._audio_stream is not None:
            return True

        if self._dictado is not None and self._dictado.activo:
            return True

        return False


    def _escucha_estado(self, estado):

        if estado == "esperando_orden":
            self._actualizar_estado_externo("te escucho...", True)

        elif estado == "reposo":
            self._actualizar_estado_externo("lista", False)


    def _escucha_al_nombre(self, restante):

        # Dijiste solo "Oddye": el tono y el estado ya avisan.
        pass


    def _escucha_al_comando(self, texto):

        # Oddye ya te oyó: muestra tu frase, la procesa y responde.
        self._empujar_mensaje_chat(texto, "user")

        self._actualizar_estado_externo("pensando...", True)

        modo_voz_antes = self.modo_voz

        if ESCUCHA_RESPONDER_EN_VOZ:
            self.modo_voz = True

        try:

            resultado = self.procesar_entrada_usuario(texto)

        finally:

            self.modo_voz = modo_voz_antes

        self._actualizar_estado_externo("lista", False)

        # Si ya se fue mostrando al hablar, no se repite.
        if not resultado.get("ya_mostrada"):

            self._empujar_mensaje_chat(
                resultado.get("respuesta", "No obtuve respuesta."),
                "ai"
            )

        # No volver a escuchar hasta que termine de hablar.
        time.sleep(0.4)

        limite = time.time() + 90

        while self._voz_hablando and time.time() < limite:
            time.sleep(0.1)


    def _avisar_escucha(self, activa):

        if self._ventana is None:
            return

        try:

            self._ventana.evaluate_js(
                "setEscuchaExterna("
                + ("true" if activa else "false")
                + ")"
            )

        except Exception:
            pass


    def alternar_escucha(self):

        if self._escucha is None:

            return {
                "ok": False,
                "activo": False,
                "mensaje": "La escucha por nombre no está disponible."
            }

        if self._escucha.activa:

            self._escucha.detener()

            return {"ok": True, "activo": False}

        if not self._escucha.iniciar():

            return {
                "ok": False,
                "activo": False,
                "mensaje": "No pude abrir el micrófono."
            }

        return {"ok": True, "activo": True}


    def estado_escucha(self):

        return {
            "disponible": self._escucha is not None,
            "activo": bool(
                self._escucha is not None and self._escucha.activa
            )
        }


    # ========================================================
    # WAKE WORD (modo antiguo con Teachable Machine; ya no se usa)
    # ========================================================

    def comando_por_voz_detectado(self):

        if self._audio_stream is not None:

            return {
                "ok": False,
                "mensaje": "Ya hay una grabación en curso."
            }

        if self._dictado is not None and self._dictado.activo:

            return {
                "ok": False,
                "mensaje": "Estoy dictando."
            }

        self._enfocar_ventana()

        self._actualizar_estado_externo(
            "escuchando...",
            True
        )

        resultado_inicio = self.iniciar_grabacion()

        if not resultado_inicio.get("ok"):

            self._actualizar_estado_externo(
                "lista",
                False
            )

            return {
                "ok": False,
                "mensaje": resultado_inicio.get(
                    "mensaje",
                    ""
                )
            }

        time.sleep(SEGUNDOS_GRABACION_COMANDO)

        resultado_transcripcion = (
            self.detener_grabacion_y_transcribir()
        )

        if not resultado_transcripcion.get("ok"):

            self._actualizar_estado_externo(
                "lista",
                False
            )

            self._empujar_mensaje_chat(
                resultado_transcripcion.get(
                    "mensaje",
                    "No entendí el comando."
                ),
                "ai"
            )

            return {
                "ok": True
            }

        texto = resultado_transcripcion["texto"]

        self._empujar_mensaje_chat(
            texto,
            "user"
        )

        self._actualizar_estado_externo(
            "pensando...",
            True
        )

        resultado = self.procesar_entrada_usuario(
            texto
        )

        self._actualizar_estado_externo(
            "lista",
            False
        )

        self._empujar_mensaje_chat(
            resultado.get(
                "respuesta",
                "No obtuve respuesta."
            ),
            "ai"
        )

        return {
            "ok": True
        }


    # ========================================================
    # CHATS GUARDADOS (barra lateral)
    # ========================================================

    def _guardar_en_chat(self, mensajes, ctx=True):

        if self._chats is None:
            return

        mensajes = [
            (rol, (contenido or "").strip())
            for rol, contenido in mensajes
            if (contenido or "").strip()
        ]

        if not mensajes:
            return

        try:

            with self._lock_chats:

                if self._chat_id is None:

                    base = next(
                        (c for r, c in mensajes if r == "user"),
                        mensajes[0][1]
                    )

                    self._chat_id = self._chats.crear(base)

                self._chats.agregar(
                    self._chat_id,
                    [
                        {
                            "role": rol,
                            "content": contenido,
                            "ctx": bool(ctx)
                        }
                        for rol, contenido in mensajes
                    ]
                )

        except Exception as error:

            print(f"[Chats] No se pudo guardar el mensaje: {error}")


    def _historial_desde(self, mensajes):

        # Solo lo que pasó por Qwen, uniendo mensajes seguidos del
        # mismo rol, y recortado para no pasarse del contexto.

        fusion = []

        for m in mensajes:

            if not m.get("ctx", True):
                continue

            rol = m.get("role")
            contenido = m.get("content")

            if rol not in ("user", "assistant") or not contenido:
                continue

            if fusion and fusion[-1]["role"] == rol:
                fusion[-1]["content"] += "\n" + contenido
            else:
                fusion.append({"role": rol, "content": contenido})

        fusion = fusion[-MAX_TURNOS_HISTORIAL * 2:]

        salida = []
        total = 0

        for m in reversed(fusion):

            total += len(m["content"])

            if total > CHATS_MAX_CARACTERES_CONTEXTO and salida:
                break

            salida.append(m)

        salida.reverse()

        return salida


    def chats_listar(self, filtro=""):

        if self._chats is None:

            return {
                "ok": False,
                "chats": [],
                "activo": None
            }

        try:

            return {
                "ok": True,
                "chats": self._chats.listar(filtro or ""),
                "activo": self._chat_id
            }

        except Exception as error:

            print(f"[Chats] Error listando: {error}")

            return {
                "ok": False,
                "chats": [],
                "activo": self._chat_id
            }


    def chat_abrir(self, chat_id):

        if self._chats is None:

            return {
                "ok": False,
                "mensaje": "Los chats guardados no están disponibles."
            }

        chat = self._chats.obtener(chat_id)

        if chat is None:

            return {
                "ok": False,
                "mensaje": "No encontré ese chat."
            }

        if self._motor_voz is not None:
            self._motor_voz.detener()

        self._chat_id = chat["id"]

        # Qwen retoma la conversación donde se quedó.
        self.historial = self._historial_desde(chat["mensajes"])

        try:
            esclavo_apps.limpiar_contexto()
        except Exception:
            pass

        return {
            "ok": True,
            "id": chat["id"],
            "titulo": chat["titulo"],
            "mensajes": [
                {
                    "role": m.get("role"),
                    "content": m.get("content", "")
                }
                for m in chat["mensajes"]
            ]
        }


    def chat_renombrar(self, chat_id, titulo):

        if self._chats is None:
            return {"ok": False}

        return {"ok": self._chats.renombrar(chat_id, titulo)}


    def chat_borrar(self, chat_id):

        if self._chats is None:
            return {"ok": False}

        era_activo = (chat_id == self._chat_id)

        ok = self._chats.borrar(chat_id)

        if ok and era_activo:

            self._chat_id = None
            self.historial = []

        return {
            "ok": ok,
            "era_activo": bool(ok and era_activo)
        }


    # ========================================================
    # NUEVO CHAT
    # ========================================================

    def nuevo_chat(self):

        self.historial = []

        # El chat se crea en disco recién con el primer mensaje.
        self._chat_id = None

        if self._motor_voz is not None:
            self._motor_voz.detener()

        try:

            esclavo_apps.limpiar_contexto()

        except Exception as error:

            print(
                "[Esclavo] No se pudo limpiar el contexto "
                f"de aplicaciones: {error}"
            )

        return {
            "ok": True
        }


    # ========================================================
    # GRABACIÓN
    # ========================================================

    def iniciar_grabacion(self):

        if (
            not os.path.isfile(WHISPER_EXE)
            or not os.path.isfile(WHISPER_MODELO)
        ):

            return {
                "ok": False,
                "mensaje": "No encontré Whisper o su modelo."
            }


        self._buffer_audio = []


        def _callback(
            indata,
            frames,
            time_info,
            status
        ):

            self._buffer_audio.append(
                indata.copy()
            )


        try:

            self._audio_stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype="float32",
                device=MICROFONO_DISPOSITIVO,
                callback=_callback
            )

            self._audio_stream.start()

            return {
                "ok": True
            }


        except Exception as e:

            self._audio_stream = None

            return {
                "ok": False,
                "mensaje": f"No se pudo abrir el micrófono: {e}"
            }


    # ========================================================
    # DETENER GRABACIÓN + WHISPER
    # ========================================================

    def detener_grabacion_y_transcribir(self):

        if self._audio_stream is None:

            return {
                "ok": False,
                "mensaje": "No había grabación en curso."
            }


        try:

            self._audio_stream.stop()
            self._audio_stream.close()

        except Exception:
            pass

        finally:

            self._audio_stream = None


        if not self._buffer_audio:

            return {
                "ok": False,
                "mensaje": "No se grabó audio (¿soltaste muy rápido?)."
            }


        audio = np.concatenate(
            self._buffer_audio,
            axis=0
        )

        self._buffer_audio = []

        # (N, 1) -> (N,)
        audio = audio.flatten()


        duracion_seg = len(audio) / 16000

        if duracion_seg < 0.3:

            return {
                "ok": False,
                "mensaje": "Grabación muy corta."
            }


        # ----------------------------------------------------
        # Energía por ventanas de 30 ms
        # ----------------------------------------------------
        #
        # En lugar de promediar toda la grabación (lo que hace
        # que el silencio "tape" la voz), se mide cada tramo
        # de 30 ms y se usa el más fuerte.
        #

        ventana = 480  # 30 ms a 16 kHz
        n_bloques = len(audio) // ventana

        if n_bloques == 0:

            return {
                "ok": False,
                "mensaje": "Grabación muy corta."
            }

        bloques = audio[: n_bloques * ventana].reshape(
            n_bloques,
            ventana
        )

        rms_bloques = np.sqrt(
            np.mean(
                np.square(bloques),
                axis=1
            )
        )

        energia_max = float(rms_bloques.max())


        print(
            f"[Whisper] Duración: {duracion_seg:.2f}s | "
            f"RMS máx: {energia_max:.5f}"
        )


        if energia_max < UMBRAL_VOZ:

            return {
                "ok": False,
                "mensaje": "No detecté voz en la grabación."
            }


        # ----------------------------------------------------
        # Recortar silencio al inicio y al final
        # ----------------------------------------------------
        #
        # El silencio largo hace que Whisper invente texto.
        #

        umbral_recorte = max(
            energia_max * 0.1,
            0.002
        )

        activos = np.where(
            rms_bloques > umbral_recorte
        )[0]

        inicio = max(0, activos[0] - 10) * ventana          # ~300 ms antes
        fin = min(n_bloques, activos[-1] + 15) * ventana    # ~450 ms después

        audio = audio[inicio:fin]


        # ----------------------------------------------------
        # Normalización
        # ----------------------------------------------------

        pico = np.max(
            np.abs(audio)
        )

        if pico > 0:

            audio = audio * (
                0.9 / pico
            )


        # ----------------------------------------------------
        # Guardar WAV
        # ----------------------------------------------------

        try:

            sf.write(
                GRABACION_WAV,
                audio,
                16000,
                subtype="PCM_16"
            )

        except Exception as e:

            return {
                "ok": False,
                "mensaje": f"Error guardando el audio: {e}"
            }


        # ----------------------------------------------------
        # Camino rápido: servidor de Whisper ya cargado (NUEVO)
        # ----------------------------------------------------
        #
        # Si el servidor no está listo o falla, se sigue con
        # whisper-cli.exe como siempre.
        #

        if (
            self._whisper_servidor is not None
            and self._whisper_servidor.listo()
        ):

            try:

                inicio_rapido = time.time()

                texto_rapido = (
                    self._whisper_servidor.transcribir(audio)
                )

                print(
                    f"[Whisper] Servidor: "
                    f"{time.time() - inicio_rapido:.2f}s"
                )

            except Exception as e:

                print(
                    "[Whisper] El servidor falló, uso "
                    f"whisper-cli: {e}"
                )

                texto_rapido = None

            if texto_rapido:

                print(
                    f"[Whisper] Texto detectado: {texto_rapido}"
                )

                return {
                    "ok": True,
                    "texto": texto_rapido
                }


        # ----------------------------------------------------
        # Ejecutar Whisper
        # ----------------------------------------------------

        try:

            inicio_whisper = time.time()

            comando_whisper = [
                WHISPER_EXE,

                "-m",
                WHISPER_MODELO,

                "-l",
                "es",

                "-t",
                str(WHISPER_HILOS),

                "-bo",
                str(WHISPER_BEST_OF),

                "-bs",
                str(WHISPER_BEAM_SIZE),

                "-nth",
                str(WHISPER_NO_SPEECH_THOLD),

                "--prompt",
                WHISPER_PROMPT,

                "-f",
                GRABACION_WAV
            ]


            print(
                "[Whisper] Iniciando transcripción..."
            )

            resultado = subprocess.run(
                comando_whisper,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=subprocess.CREATE_NO_WINDOW
            )


            tiempo_whisper = (
                time.time() - inicio_whisper
            )

            print(
                f"[Whisper] Tiempo de transcripción: "
                f"{tiempo_whisper:.2f}s"
            )

            if not resultado.stdout.strip():

                print(
                    "[Whisper] stderr:",
                    resultado.stderr[-500:]
                )


        except Exception as e:

            return {
                "ok": False,
                "mensaje": f"Error ejecutando Whisper: {e}"
            }


        # ----------------------------------------------------
        # Extraer texto
        # ----------------------------------------------------

        texto = ""

        for linea in resultado.stdout.splitlines():

            if "-->" in linea and "]" in linea:

                partes = linea.split(
                    "]",
                    1
                )

                if len(partes) == 2:

                    texto += (
                        partes[1].strip()
                        + " "
                    )


        texto = texto.strip()


        if not texto:

            return {
                "ok": False,
                "mensaje": "No pude entender el audio."
            }


        print(
            f"[Whisper] Texto detectado: {texto}"
        )


        return {
            "ok": True,
            "texto": texto
        }


    # ========================================================
    # DICTADO EN VIVO (NUEVO)
    # ========================================================

    def _empujar_dictado(self, texto):

        if self._ventana is None or not texto:
            return

        try:

            self._ventana.evaluate_js(
                "agregarTextoDictado("
                + json.dumps(texto)
                + ")"
            )

        except Exception as error:

            print(
                "[Dictado] No se pudo escribir en la "
                f"barra: {error}"
            )


    def _dictado_silencio(self):

        # Se detectó el silencio: la interfaz pasa a "terminando"
        # mientras se transcribe lo último que dijiste.

        if self._ventana is None:
            return

        try:

            self._ventana.evaluate_js(
                "dictadoDeteniendoPorSilencio()"
            )

        except Exception as error:

            print(
                "[Dictado] No se pudo avisar al frontend del "
                f"silencio: {error}"
            )


    def _dictado_terminado(self):

        # Ya se escribió todo el texto: la interfaz queda lista
        # y el texto se queda fijo en la barra.

        if self._ventana is None:
            return

        try:

            self._ventana.evaluate_js(
                "dictadoTerminado()"
            )

        except Exception as error:

            print(
                "[Dictado] No se pudo avisar al frontend del "
                f"final: {error}"
            )


    def iniciar_dictado(self):

        if self._dictado is None or self._whisper_servidor is None:

            return {
                "ok": False,
                "mensaje": "El dictado en vivo no está disponible."
            }

        if self._audio_stream is not None:

            return {
                "ok": False,
                "mensaje": "Ya hay una grabación en curso."
            }

        if not self._whisper_servidor.iniciar():

            return {
                "ok": False,
                "mensaje": (
                    "No encontré whisper-server.exe o el "
                    "modelo de Whisper."
                )
            }

        if not self._whisper_servidor.listo():

            return {
                "ok": False,
                "mensaje": (
                    "Los oídos todavía están cargando, "
                    "intenta en unos segundos."
                )
            }

        resultado = self._dictado.iniciar()

        if resultado.get("ok"):

            self._actualizar_estado_externo(
                "escuchando...",
                True
            )

        return resultado


    def detener_dictado(self):

        if self._dictado is None:

            return {
                "ok": True
            }

        # El estado vuelve a "lista" cuando el dictado avisa que
        # terminó de escribir todo el texto (_dictado_terminado).
        return self._dictado.detener()


    def limpiar_dictado(self, texto):

        # Quita autocorrecciones del texto dictado antes de
        # enviarlo. Si algo falla, devuelve el texto original.

        texto = (texto or "").strip()

        if not texto or not DICTADO_DISPONIBLE:
            return texto

        try:

            with self._lock:

                if self._cerrando:
                    return texto

                if not self.cerebro_listo:

                    if not self._encender().get("ok"):
                        return texto

                    self._iniciar_vigilante_inactividad()
                    self._iniciar_hilo_sugerencias()

            return limpiar_autocorrecciones(
                texto,
                LLAMA_URL
            )

        except Exception as error:

            print(
                "[Dictado] No se pudo limpiar el texto: "
                f"{error}"
            )

            return texto


    # ========================================================
    # PIPER
    # ========================================================

    def _notificar_voz(self, evento, mensaje=""):

        if self._ventana is None:
            return

        try:

            codigo = (
                "window.oddyeVozCallback && window.oddyeVozCallback("
                + json.dumps(evento)
                + ", "
                + json.dumps(mensaje)
                + ")"
            )

            self._ventana.evaluate_js(
                codigo
            )

        except Exception as error:

            print(
                "[Voz] No se pudo enviar callback al frontend:",
                error
            )


    def _evento_motor_voz(self, evento, mensaje=""):

        if evento == "error":
            print("[Voz] ERROR:", mensaje)

        self._voz_hablando = evento in ("iniciando", "hablando")

        if evento == "turno_completo":

            # Ya dijo toda la respuesta: se puede cerrar el texto.
            self._ui_cola.put(("voz_fin", None, None))

            return

        self._notificar_voz(evento, mensaje)


    def _hablar(self, texto):

        if not texto:
            return

        motor = self._motor_voz

        if motor is not None and motor.listo:

            motor.hablar(texto)

            return

        # Respaldo: el método anterior (más lento).
        self._hablar_con_cli(texto)


    def _hablar_con_cli(self, texto):

        if not texto:
            return

        if (
            not os.path.isfile(PIPER_MODELO)
            or not os.path.isfile(PIPER_CONFIG)
        ):

            mensaje = (
                "No encontré el modelo o la configuración de Piper."
            )

            print("[Voz] " + mensaje)

            self._notificar_voz(
                "error",
                mensaje
            )

            return


        self._voz_hablando = True

        self._notificar_voz(
            "iniciando"
        )


        try:

            print(
                "[Voz] Generando audio con Piper..."
            )

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "piper",
                    "-m",
                    PIPER_MODELO,
                    "-c",
                    PIPER_CONFIG,
                    "-f",
                    RESPUESTA_WAV,

                    "--length_scale",
                    "1.08",

                    "--noise_scale",
                    "0.667",

                    "--noise_w",
                    "0.85",

                    "--sentence_silence",
                    "0.35"
                ],
                input=texto,
                text=True,
                encoding="utf-8",
                check=True
            )


            if not os.path.isfile(
                RESPUESTA_WAV
            ):

                raise RuntimeError(
                    "Piper terminó pero no creó el archivo de audio."
                )


            audio, frecuencia = sf.read(
                RESPUESTA_WAV
            )


            cola_silencio = np.zeros(
                int(frecuencia * 0.35),
                dtype=audio.dtype
            )

            audio = np.concatenate(
                [
                    audio,
                    cola_silencio
                ]
            )


            self._notificar_voz(
                "hablando"
            )

            print(
                "[Voz] Reproduciendo audio..."
            )


            sd.play(
                audio,
                frecuencia
            )

            sd.wait()


            print(
                "[Voz] Audio terminado."
            )

            self._notificar_voz(
                "terminado"
            )


        except Exception as error:

            print(
                "[Voz] ERROR:",
                repr(error)
            )

            self._notificar_voz(
                "error",
                str(error)
            )

        finally:

            self._voz_hablando = False


    def estado_voz(self):

        return {
            "ok": True,
            "hablando": self._voz_hablando
        }


    # ========================================================
    # INTELIGENCIA PATRON — FALLO DETECTADO
    # ========================================================

    def _manejar_patron_detectado(
        self,
        nombre,
        proceso,
        fallos
    ):

        if self.sugerencias is None:
            return

        mensaje = (
            f"He detectado que has tenido problemas para abrir "
            f"{nombre}. Ya ocurrió {fallos} veces seguidas. "
            f"¿Quieres que te ayude?"
        )


        def _respuesta(respuesta):

            self._responder_patron(
                respuesta,
                nombre,
                proceso,
                fallos
            )


        self.sugerencias.mostrar_sugerencia(
            mensaje=mensaje,
            tipo="problema",
            titulo="Problema detectado",
            callback_externo=_respuesta
        )


    def _responder_patron(
        self,
        respuesta,
        nombre,
        proceso,
        fallos
    ):

        if respuesta == "ayudar":

            if self.patrones is not None:

                self.patrones.marcar_ayudado(
                    nombre
                )

            self._enfocar_ventana()

            texto_usuario = (
                f"He tenido problemas para abrir {nombre} "
                f"({fallos} intentos fallidos seguidos, "
                f"proceso esperado: {proceso}). "
                f"¿Qué puede estar pasando y qué reviso primero?"
            )


            threading.Thread(
                target=self._enviar_contexto_al_chat,
                args=(texto_usuario,),
                daemon=True
            ).start()


        elif respuesta == "ahora_no":

            print(
                f"[InteligenciaPatron] El usuario ignoró el "
                f"problema con {nombre}."
            )


    def _enviar_contexto_al_chat(
        self,
        texto_usuario
    ):

        self._empujar_mensaje_chat(
            texto_usuario,
            "user"
        )

        self._actualizar_estado_externo(
            "pensando...",
            True
        )

        resultado = self.enviar_mensaje(
            texto_usuario
        )

        self._guardar_en_chat(
            [
                ("user", texto_usuario),
                ("assistant", resultado.get("respuesta", ""))
            ],
            ctx=bool(resultado.get("ok"))
        )

        self._actualizar_estado_externo(
            "lista",
            False
        )

        self._empujar_mensaje_chat(
            resultado.get(
                "respuesta",
                "No obtuve respuesta del cerebro."
            ),
            "ai"
        )


    # ========================================================
    # INTELIGENCIA PATRON — PRUEBA
    # ========================================================

    def simular_fallo_app(
        self,
        nombre_aplicacion,
        nombre_proceso=None
    ):

        if self.observador is None:

            return {
                "ok": False,
                "mensaje": "InteligenciaPatron no está disponible."
            }

        proceso = (
            nombre_proceso
            or f"proceso_falso_{nombre_aplicacion.lower()}.exe"
        )


        resultado = self.observador.comprobar_apertura(
            nombre_aplicacion,
            proceso
        )


        if resultado.get("fallo"):

            patron = resultado.get(
                "patron",
                {}
            )

            if patron.get("detectado"):

                self._manejar_patron_detectado(
                    nombre_aplicacion,
                    proceso,
                    patron.get(
                        "fallos",
                        0
                    )
                )


        return resultado


    # ========================================================
    # INTELIGENCIA PATRON — SUGERENCIAS
    # ========================================================

    def _iniciar_hilo_sugerencias(self):

        if self.sugerencias is None:
            return

        if self._hilo_sugerencias_activo:
            return

        self._hilo_sugerencias_activo = True

        hilo = threading.Thread(
            target=self._bucle_sugerencias,
            daemon=True
        )

        hilo.start()


    def _bucle_sugerencias(self):

        try:

            while not self._cerrando:

                time.sleep(
                    INTERVALO_REVISION_SUGERENCIAS
                )

                if self._cerrando:
                    return

                if self.sugerencias is None:
                    return

                if not self.sugerencias.puede_sugerir():
                    continue

                tipo_info = (
                    self.sugerencias.seleccionar_tipo()
                )

                if tipo_info["tipo"] not in (
                    "general",
                    "aleatoria"
                ):

                    continue

                mensaje = random.choice(
                    SUGERENCIAS_GENERALES
                )


                def _respuesta(
                    respuesta,
                    _mensaje=mensaje
                ):

                    self._responder_sugerencia_general(
                        respuesta,
                        _mensaje
                    )


                self.sugerencias.mostrar_sugerencia(
                    mensaje=mensaje,
                    tipo=tipo_info["tipo"],
                    titulo="Asistente IA",
                    callback_externo=_respuesta
                )

        finally:

            self._hilo_sugerencias_activo = False


    def _responder_sugerencia_general(
        self,
        respuesta,
        mensaje_sugerencia
    ):

        if respuesta == "ayudar":

            self._enfocar_ventana()

            threading.Thread(
                target=self._enviar_sugerencia_al_chat,
                args=(mensaje_sugerencia,),
                daemon=True
            ).start()

        elif respuesta == "ahora_no":

            print(
                "[InteligenciaPatron] El usuario ignoró la "
                "sugerencia general."
            )


    def _enviar_sugerencia_al_chat(
        self,
        mensaje_sugerencia
    ):

        self._empujar_mensaje_chat(
            mensaje_sugerencia,
            "ai"
        )

        self._actualizar_estado_externo(
            "pensando...",
            True
        )


        prompt_interno = (
            "Tú mismo le acabas de decir esto al usuario: "
            f"\"{mensaje_sugerencia}\". El usuario respondió que sí "
            "quiere ayuda. NO repitas esa pregunta. En 1 o 2 frases, "
            "continúa la conversación ofreciendo ayuda concreta y "
            "específica sobre ese tema (opciones reales, no "
            "genéricas), en tono natural, como si siguieras hablando."
        )


        resultado = self.enviar_mensaje(
            prompt_interno
        )

        self._guardar_en_chat(
            [
                ("assistant", mensaje_sugerencia),
                ("assistant", resultado.get("respuesta", ""))
            ],
            ctx=bool(resultado.get("ok"))
        )


        self._actualizar_estado_externo(
            "lista",
            False
        )


        self._empujar_mensaje_chat(
            resultado.get(
                "respuesta",
                "No obtuve respuesta del cerebro."
            ),
            "ai"
        )


# ============================================================
# MAIN
# ============================================================

def limpiar_procesos_viejos():

    # Cierra copias de Oddye y servidores (cerebro / oídos) que hayan
    # quedado vivos de una ejecución anterior. Cada uno ocupa varios
    # GB de RAM aunque no se vea ninguna ventana.
    if not RECURSOS_DISPONIBLE:
        return

    try:

        copias = recursos.cerrar_instancias_viejas(
            os.path.abspath(__file__)
        )

        servidores = recursos.limpiar_huerfanos(
            [LLAMA_SERVER, WHISPER_SERVER_EXE],
            claves=[
                os.path.basename(CEREBRO_MODELO),
                os.path.basename(WHISPER_MODELO)
            ]
        )

        if copias or servidores:

            print(
                f"[Memoria] Cerré {copias} copia(s) vieja(s) de Oddye "
                f"y {servidores} servidor(es) que seguían abiertos."
            )

    except Exception as error:

        print(f"[Memoria] No se pudo limpiar procesos viejos: {error}")


def main():

    limpiar_procesos_viejos()

    api = Api()

    frontend_path = os.path.join(
        BASE_DIR,
        "frontend",
        "index.html"
    )


    # ========================================================
    # UNA SOLA VENTANA
    # ========================================================

    window = webview.create_window(
        "Mi IA Offline",
        frontend_path,
        js_api=api,
        width=1100,
        height=750,
        min_size=(760, 560),
        background_color="#12141A"
    )

    api.set_ventana(
        window
    )


    # ========================================================
    # CIERRE
    # ========================================================

    window.events.closing += (
        api.apagar_cerebro
    )


    # ========================================================
    # INICIAR WEBVIEW
    # ========================================================

    webview.start(
        debug=True
    )


# ============================================================
# PUNTO DE ENTRADA
# ============================================================

if __name__ == "__main__":
    main()