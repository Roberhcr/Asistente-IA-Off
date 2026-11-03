"""
eda.py
Análisis exploratorio del dataset crudo (data/raw/dataset_v0.jsonl).

Produce:
  reports/eda_resumen.json     -> estadísticas descriptivas
  reports/figures/fig_eda_*.png -> figuras para el informe

Si llama-server está activo (http://127.0.0.1:8080), cuenta además los tokens
reales con el tokenizador de Qwen3 mediante el endpoint /tokenize.

Uso:
    python src/visualization/eda.py
"""

import json
import os
import re
import unicodedata
import urllib.request
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENTRADA = os.path.join(RAIZ, "data", "raw", "dataset_v0.jsonl")
FIG_DIR = os.path.join(RAIZ, "reports", "figures")
RESUMEN = os.path.join(RAIZ, "reports", "eda_resumen.json")
LLAMA_URL = "http://127.0.0.1:8080"

AZUL = "#2a78d6"
NARANJA = "#eb6834"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
GRID = "#e4e3df"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID,
    "axes.labelcolor": TINTA_2, "xtick.color": TINTA_2, "ytick.color": TINTA_2,
    "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 200,
})


def normalizar_clave(texto):
    """Clave para detectar duplicados: minúsculas, sin tildes ni puntuación."""
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def palabras(texto):
    return re.findall(r"\w+", texto.lower())


def contar_tokens_llama(textos):
    """Devuelve lista de conteos de tokens o None si llama-server no está activo."""
    try:
        urllib.request.urlopen(LLAMA_URL + "/health", timeout=1)
    except Exception:
        return None
    conteos = []
    for t in textos:
        req = urllib.request.Request(
            LLAMA_URL + "/tokenize", data=json.dumps({"content": t}).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        conteos.append(len(json.loads(urllib.request.urlopen(req).read())["tokens"]))
    return conteos


def main():
    df = pd.read_json(ENTRADA, lines=True)
    os.makedirs(FIG_DIR, exist_ok=True)

    df["n_palabras"] = df["instruccion"].apply(lambda t: len(palabras(t)))
    df["n_caracteres"] = df["instruccion"].str.len()
    df["clave"] = df["instruccion"].apply(normalizar_clave)

    tokens = contar_tokens_llama(df["instruccion"].tolist())
    if tokens:
        df["n_tokens"] = tokens

    # ---------- estadísticas ----------
    por_intencion = df["intencion"].value_counts()
    dup_exactos = int(df.duplicated(subset=["instruccion"]).sum())
    dup_normalizados = int(df.duplicated(subset=["clave"]).sum())
    dup_por_intencion = df[df.duplicated(subset=["clave"])]["intencion"].value_counts()
    conflictos = df.groupby("clave")["intencion"].nunique()
    conflictos = int((conflictos > 1).sum())

    vocab = Counter(w for t in df["instruccion"] for w in palabras(t))
    total_palabras = sum(vocab.values())

    longitud = df.groupby("intencion")["n_palabras"].agg(["mean", "std", "min", "median", "max"]).round(2)

    cobertura = {}
    for intencion, grupo in df.groupby("intencion"):
        valores = {}
        for p in grupo["parametros"]:
            for k, v in p.items():
                if isinstance(v, list):
                    v = len(v)
                valores.setdefault(k, set()).add(json.dumps(v, ensure_ascii=False))
        cobertura[intencion] = {k: len(v) for k, v in valores.items()}

    resumen = {
        "total_registros": int(len(df)),
        "num_intenciones": int(df["intencion"].nunique()),
        "por_intencion": por_intencion.to_dict(),
        "porcentaje_por_intencion": (por_intencion / len(df) * 100).round(1).to_dict(),
        "razon_desbalance_max_min": round(por_intencion.max() / por_intencion.min(), 2),
        "por_categoria": df["categoria"].value_counts().to_dict(),
        "por_origen": df["origen"].value_counts().to_dict(),
        "por_registro": df["registro"].value_counts().to_dict(),
        "con_contexto": int(df["contexto"].notna().sum()),
        "palabras": df["n_palabras"].describe().round(2).to_dict(),
        "caracteres": df["n_caracteres"].describe().round(2).to_dict(),
        "tokens_qwen3": df["n_tokens"].describe().round(2).to_dict() if tokens else "no medido (llama-server inactivo)",
        "longitud_por_intencion": longitud.to_dict(orient="index"),
        "duplicados_exactos": dup_exactos,
        "duplicados_normalizados": dup_normalizados,
        "instrucciones_unicas_normalizadas": int(df["clave"].nunique()),
        "duplicados_por_intencion": dup_por_intencion.to_dict(),
        "claves_con_intenciones_en_conflicto": conflictos,
        "vocabulario": len(vocab),
        "total_palabras": total_palabras,
        "type_token_ratio": round(len(vocab) / total_palabras, 3),
        "top_palabras": vocab.most_common(20),
        "cobertura_parametros": cobertura,
    }
    with open(RESUMEN, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2, default=str)

    # ---------- Figura A: ejemplos por intención ----------
    orden = por_intencion.sort_values()
    unicos = df.drop_duplicates(subset=["clave"])["intencion"].value_counts().reindex(orden.index)
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    y = np.arange(len(orden))
    ax.barh(y, orden.values, color=AZUL, height=0.62, label="Registros totales")
    ax.barh(y, unicos.values, color=NARANJA, height=0.28, label="Instrucciones únicas")
    for i, (tot, uni) in enumerate(zip(orden.values, unicos.values)):
        ax.text(tot + 2, i, f"{tot} ({uni} únicas)", va="center", fontsize=8, color=TINTA_2)
    ax.set_yticks(y, orden.index, fontsize=8.5, color=TINTA)
    ax.set_xlabel("Número de ejemplos")
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_xlim(0, orden.max() * 1.32)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig_eda_distribucion_intenciones.png"), facecolor="white")
    plt.close(fig)

    # ---------- Figura B: longitud de instrucciones por intención ----------
    orden_med = df.groupby("intencion")["n_palabras"].median().sort_values().index
    datos = [df.loc[df["intencion"] == i, "n_palabras"].values for i in orden_med]
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    bp = ax.boxplot(datos, orientation="horizontal", patch_artist=True, widths=0.55,
                    medianprops=dict(color=TINTA, linewidth=1.4),
                    flierprops=dict(marker="o", markersize=3, markerfacecolor=TINTA_2, markeredgewidth=0))
    for caja in bp["boxes"]:
        caja.set(facecolor=AZUL, alpha=0.35, edgecolor=AZUL)
    for parte in ("whiskers", "caps"):
        for l in bp[parte]:
            l.set(color=TINTA_2, linewidth=0.8)
    ax.set_yticks(range(1, len(orden_med) + 1), orden_med, fontsize=8.5, color=TINTA)
    ax.set_xlabel("Longitud de la instrucción (palabras)")
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig_eda_longitud_intenciones.png"), facecolor="white")
    plt.close(fig)

    # ---------- Figura C: registro lingüístico ----------
    etiquetas = {"tu": "Tuteo", "vos": "Voseo", "usted": "Usted", "perifrasis": "Perífrasis\n(quiero, puedes…)"}
    reg = df["registro"].value_counts()
    fig, ax = plt.subplots(figsize=(6.2, 2.8))
    x = np.arange(len(reg))
    ax.bar(x, reg.values, color=AZUL, width=0.55)
    for i, v in enumerate(reg.values):
        ax.text(i, v + 6, f"{v} ({v / len(df) * 100:.1f} %)", ha="center", fontsize=8, color=TINTA_2)
    ax.set_xticks(x, [etiquetas[r] for r in reg.index], fontsize=8.5, color=TINTA)
    ax.set_ylabel("Número de ejemplos")
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_ylim(0, reg.max() * 1.18)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig_eda_registro_linguistico.png"), facecolor="white")
    plt.close(fig)

    print(json.dumps({k: resumen[k] for k in [
        "total_registros", "num_intenciones", "razon_desbalance_max_min", "duplicados_exactos",
        "duplicados_normalizados", "instrucciones_unicas_normalizadas", "claves_con_intenciones_en_conflicto",
        "vocabulario", "type_token_ratio", "por_origen", "por_registro", "palabras"]},
        ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
