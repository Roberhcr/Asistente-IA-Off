# Oddye: asistente inteligente de escritorio sin conexión

Oddye es un asistente para Windows que funciona **sin Internet**. Entiende órdenes en español, escritas o habladas, y las convierte en acciones sobre la computadora: abrir y cerrar programas, abrir carpetas, ejecutar comandos del sistema y conversar. Todo el procesamiento ocurre en el equipo.

- **Cerebro:** Qwen3-4B (GGUF Q4_K_M) en llama.cpp (`llama-server`).
- **Oídos:** whisper.cpp con el modelo Whisper base.
- **Voz:** Piper con la voz `es_MX-claude-high`.
- **Interfaz:** pywebview (HTML, CSS y JavaScript).

Proyecto de la asignatura de Inteligencia Artificial, Universidad Nacional de Ingeniería (UNI), Managua, Nicaragua, 2026.
Autores: Br. Robertha Valeria Cabrera Ramos y Br. Kenneth Alexander Guzmán Cisnero. Docente: Ing. Martín Loza.

## Requisitos

- Windows 10 u 11 de 64 bits. No requiere tarjeta gráfica; si hay una GPU dedicada compatible, la aprovecha.
- Python 3.9 o superior.
- 8 GB de RAM como mínimo (recomendado 16 GB) y unos 3 GB libres en disco para los modelos.

## Instalación

Los modelos de IA pesan más de lo que GitHub permite (100 MB por archivo), así que no están en el repositorio. El script `instalar_modelos.ps1` los descarga en las carpetas correctas.

```powershell
git clone https://github.com/Roberhcr/Asistente-IA-Off.git
cd Asistente-IA-Off

# 1. Descargar los modelos (Qwen3-4B, Whisper base y la voz de Piper)
powershell -ExecutionPolicy Bypass -File .\instalar_modelos.ps1

# 2. Crear el entorno de Python e instalar dependencias
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# 3. Abrir Oddye
python main.py
```

Los motores (`llama-server.exe` y `whisper-server.exe`) sí vienen en la carpeta `Motores/`.

## Uso

- **Texto:** escribe la orden en el chat, por ejemplo “abre Word” o “abrí la carpeta de descargas”.
- **Voz:** di “Oddye” seguido de la orden (“Oddye, abre Spotify”). Si solo dices “Oddye”, suena un tono y escucha la siguiente frase.
- **Dictado:** el micrófono de la interfaz transcribe en vivo, frase por frase.
- **Chats:** cada conversación se guarda en `Chats/` y puede reabrirse, renombrarse o borrarse.
- **Ajustes de rendimiento:** límites de RAM y GPU, tamaño de respuestas y minutos de inactividad en `Config/ajustes.py`.

## Estructura

```
main.py                    Aplicación: arranque del cerebro, chat, voz, dictado y enrutamiento de órdenes
escucha.py                 Escucha continua del nombre “Oddye” (detección de voz + Whisper)
voz.py                     Motor de voz Piper: carga única y síntesis por frases
dictado.py                 Servidor Whisper y dictado en vivo; limpieza de autocorrecciones con Qwen
chats.py                   Guardado y búsqueda de conversaciones
Config/ajustes.py          Ajustes de memoria, GPU, contexto y respuestas
Config/recursos.py         Detección de GPU, plan de arranque de llama-server y vigilante de memoria
Config/diagnostico_memoria.py   Informe de consumo de RAM (uso desde terminal)
Esclavo/                   Acciones: aplicaciones, carpetas y comandos del sistema (lista permitida)
InteligenciaPatron/        Observador de procesos, memoria de eventos, patrones y sugerencias
frontend/                  Interfaz (HTML/CSS/JS); libs/ y “Modelo de voz/” son la palabra de activación
                           anterior (TensorFlow.js), reemplazada por escucha.py
Motores/                   llama.cpp (b10588, CPU x64) y whisper.cpp (x64)
Modelos/, Voz (Piper)/     Se llenan con instalar_modelos.ps1

data/raw/                  Conjunto de datos de instrucciones (dataset_v0.jsonl, complemento_v1.jsonl)
data/processed/            Particiones train / val / test / test_voz, banco few-shot y esquema de salida
src/                       Pipeline de datos, EDA, modelos de referencia e intérprete con Qwen3-4B
reports/                   Figuras y métricas
tests/                     Pruebas del pipeline de datos
```

## Reproducir el pipeline de datos y la evaluación

```bash
pip install -r requirements-datos.txt
python src/data/make_dataset.py
python src/visualization/eda.py
python src/features/build_features.py
python src/models/baseline.py
python src/models/evaluar_reglas.py
pytest -q

# Intérprete con el LLM (requiere llama-server activo en el puerto 8080)
python src/models/predict_model.py --evaluar test
python src/models/predict_model.py --evaluar test_voz
```

## Privacidad

Las conversaciones (`Chats/`), la memoria de patrones (`InteligenciaPatron/memoria_patrones.json`) y los audios temporales se quedan en el equipo y están excluidos del repositorio en `.gitignore`.

## Licencias de terceros

Qwen3-4B: Apache-2.0 · llama.cpp, whisper.cpp y Whisper: MIT · piper-tts: GPL-3.0 o posterior · voz es_MX-claude-high: datos con licencia Apache-2.0. Conjunto de datos propio: CC BY 4.0.
