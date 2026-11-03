"""
diagramas.py
Genera los diagramas del informe con el mismo estilo visual de las figuras
originales (cajas gris -> azul -> verde).

Uso:
    python src/visualization/diagramas.py
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIG = os.path.join(RAIZ, "reports", "figures")
GRIS, AZUL, VERDE = "#444441", "#0c447c", "#085041"
TXT = {"gris": "#e8e8e4", "azul": "#d6e4f3", "verde": "#bfe9da"}
COLOR = {"gris": GRIS, "azul": AZUL, "verde": VERDE}
FLECHA = "#8a8a86"


def caja(ax, x, y, w, h, texto, tipo="azul", titulo=None, fs=9):
    if tipo == "plan":  # componente planificado: borde discontinuo, sin relleno
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.12",
                                    fc="#f4f4f2", ec=GRIS, lw=1.2, ls="--"))
        ax.text(x + w / 2, y + h / 2, texto, color="#2b2b29", fontsize=fs, ha="center",
                va="center", linespacing=1.35)
        return
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.12",
                                fc=COLOR[tipo], ec="none"))
    if titulo:
        ax.text(x + 0.15, y + h - 0.22, titulo, color="white", fontsize=fs + 1, fontweight="bold",
                va="top", ha="left")
        lineas = titulo.count("\n") + 1
        ax.text(x + 0.15, y + h - 0.42 - 0.22 * lineas, texto, color=TXT[tipo], fontsize=fs - 0.5, va="top",
                ha="left", linespacing=1.45)
    else:
        ax.text(x + w / 2, y + h / 2, texto, color=TXT[tipo], fontsize=fs, ha="center",
                va="center", linespacing=1.35)


def flecha(ax, x1, y1, x2, y2, estilo="-|>", ls="-"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=estilo, color=FLECHA, lw=1.1, linestyle=ls,
                                shrinkA=0, shrinkB=0, mutation_scale=10))


def lienzo(w, h):
    fig, ax = plt.subplots(figsize=(w, h), dpi=220)
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def guardar(fig, nombre):
    fig.savefig(os.path.join(FIG, nombre), facecolor="white", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)


def crisp():
    fig, ax = lienzo(10, 4.0)
    w, h = 2.9, 1.5
    fases = [
        ("1. Comprensión del negocio\ny de los datos", "Caso de uso, requerimientos,\ncatálogo de intenciones", "gris"),
        ("2. Ingeniería de datos", "Dataset, EDA y\npreprocesamiento", "azul"),
        ("3. Ingeniería del modelo", "Selección de Qwen3-4B y\nestrategia few-shot + JSON", "azul"),
        ("6. Monitoreo y\nmantenimiento", "Registro local, ajustes\ndel prompt y del dataset", "verde"),
        ("5. Despliegue", "Integración en la aplicación\nde escritorio (incrementos)", "azul"),
        ("4. Evaluación del modelo", "Métricas en test y test_voz,\npruebas funcionales", "azul"),
    ]
    pos = [(0.2, 2.3), (3.55, 2.3), (6.9, 2.3), (0.2, 0.2), (3.55, 0.2), (6.9, 0.2)]
    for (t, d, tipo), (x, y) in zip(fases, pos):
        caja(ax, x, y, w, h, d, tipo, titulo=t, fs=8.5)
    flecha(ax, 3.1, 3.05, 3.55, 3.05)
    flecha(ax, 6.45, 3.05, 6.9, 3.05)
    flecha(ax, 8.35, 2.3, 8.35, 1.7)
    flecha(ax, 6.9, 0.95, 6.45, 0.95)
    flecha(ax, 3.55, 0.95, 3.1, 0.95)
    flecha(ax, 1.65, 1.7, 1.65, 2.3, ls="--")
    ax.text(1.75, 2.0, "retroalimentación", fontsize=7, color="#5a5a56", va="center")
    guardar(fig, "fig_crisp_ml.png")


def incrementos():
    fig, ax = lienzo(10, 4.3)
    w, h = 3.0, 1.75
    datos = [
        ("Incremento 1 · Completado", "Asistente.py (consola)\n– Qwen3-4B en llama-server\n– Voz a texto: whisper.cpp\n– Texto a voz: Piper", "verde"),
        ("Incremento 2 · Completado", "main.py + frontend\n– Interfaz pywebview\n– Memoria corta (8 turnos)\n– Modo pensamiento y modo voz", "verde"),
        ("Incremento 3 · Parcial", "Acciones y voz manos libres\n– Reglas: apps, carpetas, comandos\n– Palabra de activación “Oddye”\n– Whisper optimizado y dictado", "azul"),
        ("Incremento 4 · Parcial", "Patrones y sugerencias\n– ObservadorPC (psutil)\n– Memoria JSON de eventos\n– Notificaciones y sugerencias", "azul"),
        ("Incremento 5 · En diseño", "Intérprete LLM y contexto\n– Dataset y few-shot + JSON\n– Registro de todas las acciones\n– Archivos, rutinas, “¿qué hacía?”", "gris"),
    ]
    pos = [(0.1, 2.45), (3.45, 2.45), (6.8, 2.45), (6.8, 0.15), (3.45, 0.15)]
    for (t, d, tipo), (x, y) in zip(datos, pos):
        caja(ax, x, y, w, h, d, tipo, titulo=t, fs=8.5)
    flecha(ax, 3.1, 3.32, 3.45, 3.32)
    flecha(ax, 6.45, 3.32, 6.8, 3.32)
    flecha(ax, 8.3, 2.45, 8.3, 1.9)
    flecha(ax, 6.8, 1.02, 6.45, 1.02)
    for y, tipo, txt in [(1.45, "verde", "Completado"), (1.0, "azul", "Parcial (funciona en main.py)"), (0.55, "gris", "En diseño (datos listos)")]:
        ax.add_patch(FancyBboxPatch((0.25, y), 0.22, 0.22, boxstyle="round,pad=0,rounding_size=0.04",
                                    fc=COLOR[tipo], ec="none"))
        ax.text(0.57, y + 0.11, txt, fontsize=8.2, va="center", color="#333")
    guardar(fig, "fig_incrementos.png")


def preprocesamiento():
    fig, ax = lienzo(10, 3.7)
    w, h = 2.9, 1.15
    pasos = [
        ("Datos crudos\n1 056 (v0) + 52 (v1) = 1 108", "gris"),
        ("Normalización Unicode y\nvalidación de esquema JSON\n(0 registros inválidos)", "azul"),
        ("Deduplicación por clave\nnormalizada (−159)\n949 instrucciones únicas", "azul"),
        ("Formatos finales: JSONL,\nbanco few-shot (chat)\ny esquema de salida", "verde"),
        ("Variantes tipo voz\n+150 en train\n112 en test_voz", "azul"),
        ("Partición estratificada\n70/15/15 (semilla 42)\n664 / 142 / 143", "azul"),
    ]
    pos = [(0.2, 2.35), (3.55, 2.35), (6.9, 2.35), (0.2, 0.3), (3.55, 0.3), (6.9, 0.3)]
    for (t, tipo), (x, y) in zip(pasos, pos):
        caja(ax, x, y, w, h, t, tipo, fs=8.5)
    flecha(ax, 3.1, 2.92, 3.55, 2.92)
    flecha(ax, 6.45, 2.92, 6.9, 2.92)
    flecha(ax, 8.35, 2.35, 8.35, 1.45)
    flecha(ax, 6.9, 0.87, 6.45, 0.87)
    flecha(ax, 3.55, 0.87, 3.1, 0.87)
    guardar(fig, "fig_preprocesamiento.png")


def arquitectura():
    fig, ax = lienzo(10.9, 5.0)
    h = 0.95
    caja(ax, 0.1, 3.75, 1.75, h, "Usuario\n“Oddye” + voz\no texto", "gris", fs=8.5)
    caja(ax, 2.2, 3.75, 1.75, h, "Voz a texto\nwhisper.cpp", "azul", fs=8.5)
    caja(ax, 4.3, 3.75, 2.55, h, "Nivel 1: reglas (Esclavo)\napps, carpetas, comandos\n(respuesta en milisegundos)", "azul", fs=8.5)
    caja(ax, 7.2, 3.75, 3.2, h, "Nivel 2: Qwen3-4B few-shot\n+ JSON Schema (evaluado:\n95,1 %; sin integrar)", "plan", fs=8.5)
    caja(ax, 7.2, 2.2, 3.2, h, "Validador de esquema\ninválido → “ambigua”\n(pide aclaración)", "plan", fs=8.5)
    caja(ax, 3.95, 2.2, 2.9, h, "Ejecutor (lista blanca)\napagar/reiniciar: 30 s\npara cancelar", "azul", fs=8.5)
    caja(ax, 0.1, 2.2, 3.5, h, "Respuesta: texto en la interfaz\ny voz con Piper; si no es\nacción → conversación con Qwen3", "verde", fs=8.5)
    caja(ax, 3.95, 0.3, 2.9, h, "ObservadorPC (psutil)\nverifica la apertura", "azul", fs=8.5)
    caja(ax, 7.2, 0.3, 3.2, h, "GestorPatrones\nmemoria_patrones.json\nfallos repetidos → sugerencia", "azul", fs=8.5)
    flecha(ax, 1.85, 4.22, 2.2, 4.22)
    flecha(ax, 3.95, 4.22, 4.3, 4.22)
    flecha(ax, 6.85, 4.22, 7.2, 4.22)
    flecha(ax, 5.6, 3.75, 5.6, 3.15)
    flecha(ax, 8.8, 3.75, 8.8, 3.15)
    flecha(ax, 7.2, 2.67, 6.85, 2.67)
    flecha(ax, 3.95, 2.67, 3.6, 2.67)
    flecha(ax, 5.4, 2.2, 5.4, 1.25)
    flecha(ax, 6.85, 0.77, 7.2, 0.77)
    ax.plot([10.4, 10.7, 10.7], [0.77, 0.77, 1.75], color=FLECHA, lw=1.0, ls="--")
    ax.plot([10.7, 1.85, 1.85], [1.75, 1.75, 2.2], color=FLECHA, lw=1.0, ls="--")
    flecha(ax, 1.85, 1.95, 1.85, 2.2, ls="--")
    ax.text(8.9, 1.55, "sugerencia por notificación de Windows", fontsize=7, color="#5a5a56", ha="center")
    ax.add_patch(FancyBboxPatch((0.15, 0.95), 0.22, 0.22, boxstyle="round,pad=0,rounding_size=0.04", fc=AZUL, ec="none"))
    ax.text(0.45, 1.06, "Implementado", fontsize=8, va="center", color="#333")
    ax.add_patch(FancyBboxPatch((0.15, 0.5), 0.22, 0.22, boxstyle="round,pad=0,rounding_size=0.04", fc="#f4f4f2", ec=GRIS, ls="--"))
    ax.text(0.45, 0.61, "Pendiente de integrar", fontsize=8, va="center", color="#333")
    guardar(fig, "fig_arquitectura_interprete.png")


if __name__ == "__main__":
    os.makedirs(FIG, exist_ok=True)
    crisp()
    incrementos()
    preprocesamiento()
    arquitectura()
    print("Diagramas generados en", FIG)
