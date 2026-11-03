"""
Config/ajustes.py - TODOS los ajustes de rendimiento y recursos de Oddye

Este es el único lugar que necesitas tocar para afinar el consumo de
RAM, el tamaño de las respuestas y la escucha. main.py lee este archivo
al arrancar; lo que pongas aquí manda sobre los valores de respaldo que
trae main.py. Si borras una línea, se usa el valor de respaldo.

Después de cambiar algo, cierra y vuelve a abrir Oddye.
"""

# ============================================================
# MEMORIA (RAM)
# ============================================================

# Máximo de la RAM TOTAL del equipo que puede usar Oddye (cerebro,
# oídos, voz y ventana, todo junto). Si se pasa, libera memoria.
# En un equipo de 16 GB: 30% -> 4.8 GB.
RAM_MAXIMA_PORCENTAJE = 30

# Cada cuántos segundos mide el consumo.
MEMORIA_INTERVALO_SEG = 15

# Minutos sin usar Oddye antes de apagar el cerebro (libera ~3 GB).
# Se vuelve a encender solo al escribirle o hablarle.
MINUTOS_INACTIVIDAD = 5

# Modo ahorro extremo: usa un modelo más pequeño (si lo tienes en la
# carpeta Modelos/Cerebro 4B (llama.cpp)/). Con Qwen3-1.7B toda la IA
# cabe en unos 2.5-3 GB, pero responde peor que el 4B.
MODO_AHORRO_EXTREMO = False
NOMBRE_MODELO_LIGERO = "Qwen3-1.7B-Q4_K_M.gguf"


# ============================================================
# GPU
# ============================================================

# Si hay una GPU DEDICADA (NVIDIA / AMD) y tu llama-server trae soporte
# (CUDA o Vulkan), máximo de su memoria que se usa para el cerebro.
# Una GPU integrada (Intel Iris/UHD) comparte la RAM: no se usa.
GPU_MAXIMA_PORCENTAJE = 70


# ============================================================
# CEREBRO (Qwen): contexto y tamaño de las respuestas
# ============================================================

# Memoria de conversación en tokens. Más = recuerda más y gasta más RAM.
# Si no cabe en el límite de RAM, se reduce solo.
CTX_SIZE = 4096

# Tope de tokens por tipo de respuesta (1 palabra ~ 1.6 tokens).
MAX_TOKENS_RESPUESTA = 320      # preguntas normales por texto
MAX_TOKENS_LARGO = 700          # cuentos, redacciones, resúmenes, código
MAX_TOKENS_VOZ = 200            # respuestas habladas normales
MAX_TOKENS_VOZ_LARGO = 450      # cuentos, etc. hablados
MAX_TOKENS_PENSANDO = 950     # modo pensamiento

# Para que no repita palabras ni frases (1.0 = sin penalización).
REPETICION_PENALIZACION = 1.12

# Cuántos turnos de conversación se le mandan a Qwen en cada mensaje.
MAX_TURNOS_HISTORIAL = 10


# ============================================================
# OÍDOS (Whisper)
# ============================================================

# Más alto = más preciso pero más lento y gasta algo más.
# Si se pone lento, baja los dos a 2.
WHISPER_SERVER_BEAM = 5
WHISPER_SERVER_BEST_OF = 5


# ============================================================
# ESCUCHA POR NOMBRE ("Oddye")
# ============================================================

# True = al abrir Oddye ya queda escuchando su nombre.
ESCUCHA_AL_INICIAR = True

# Sube si se activa con ruido o con gente hablando lejos; bájalo si no
# te oye (rango útil: 0.006 - 0.03).
ESCUCHA_UMBRAL_MINIMO = 0.018

# Segundos de silencio para dar por terminada una frase.
ESCUCHA_SILENCIO_FIN_SEG = 2

# Si dices solo "Oddye", cuántos segundos espera tu orden.
ESCUCHA_ESPERA_ORDEN_SEG = 7.0


# ============================================================
# REGISTROS (archivos de texto para diagnosticar)
# ============================================================

# memoria_log.txt: quién gasta cuánta RAM.
REGISTRO_MEMORIA = True

# escucha_log.txt: qué oyó Whisper y qué hizo Oddye con eso.
REGISTRO_ESCUCHA = True