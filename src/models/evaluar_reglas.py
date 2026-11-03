"""
evaluar_reglas.py
Evalúa el intérprete por reglas que usa hoy la aplicación (módulo Esclavo:
intenciones.py + acciones_apps.py) sobre los conjuntos de prueba del dataset.

Reproduce el mismo orden que main.py -> procesar_entrada_usuario():
  1. acciones_apps.interpretar_apertura()  -> abrir_app / cerrar_app
  2. intenciones.detectar_intencion()      -> sistema / carpeta / programa / chat
  3. "chat" se envía al LLM como conversación  -> conversacion_general

Solo importa funciones de interpretación; NO ejecuta ninguna acción.

Uso (desde la raíz del proyecto, donde está la carpeta Esclavo/):
    python src/models/evaluar_reglas.py [ruta_a_Esclavo]
"""
import json
import os
import sys

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROC = os.path.join(RAIZ, "data", "processed")
REPORTE = os.path.join(RAIZ, "reports", "reglas_resultados.json")
ESCLAVO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RAIZ, "Esclavo")
sys.path.insert(0, ESCLAVO)

import acciones_apps  # noqa: E402
import intenciones  # noqa: E402

INTENCIONES_ACCION = {"abrir_aplicacion", "cerrar_aplicacion", "abrir_carpeta", "ejecutar_comando"}


def predecir(texto, contexto=None):
    """Devuelve (intencion, parametros) tal como los decidiría main.py."""
    acciones_apps.limpiar_contexto()
    if contexto and contexto.startswith("Última aplicación abierta:"):
        acciones_apps.ULTIMA_APP = contexto.split(":", 1)[1].strip()

    ia = acciones_apps.interpretar_apertura(texto)
    if ia and ia.get("accion") == "abrir_app":
        return "abrir_aplicacion", {"aplicacion": ia["nombre"]}
    if ia and ia.get("accion") == "cerrar_app":
        return "cerrar_aplicacion", {"aplicacion": ia["nombre"]}

    di = intenciones.detectar_intencion(texto)
    tipo = di.get("intencion")
    if tipo == "sistema":
        return "ejecutar_comando", {"comando": di["accion"]}
    if tipo == "carpeta":
        return "abrir_carpeta", {"carpeta": intenciones_a_clave(di["nombre"])}
    if tipo == "programa":
        return "abrir_aplicacion", {"aplicacion": di["nombre"]}
    return "conversacion_general", {}


def intenciones_a_clave(nombre):
    return (nombre.replace("á", "a").replace("é", "e").replace("í", "i")
            .replace("ó", "o").replace("ú", "u"))


def evaluar(nombre):
    df = pd.read_json(os.path.join(PROC, f"{nombre}.jsonl"), lines=True)
    preds = [predecir(r["instruccion"], r["contexto"] if isinstance(r["contexto"], str) else None)
             for _, r in df.iterrows()]
    df["pred"] = [p[0] for p in preds]
    df["pred_param"] = [p[1] for p in preds]
    acc = df[df["intencion"].isin(INTENCIONES_ACCION)]

    def params_ok(r):
        esperado = {k: v for k, v in r["parametros"].items() if k != "requiere_confirmacion"}
        return r["pred"] == r["intencion"] and r["pred_param"] == esperado

    no_accion = df[~df["intencion"].isin(INTENCIONES_ACCION)]
    falsas = no_accion[no_accion["pred"].isin(INTENCIONES_ACCION)]
    res = {
        "n": int(len(df)),
        "exactitud_global": round(accuracy_score(df["intencion"], df["pred"]), 4),
        "f1_macro_global": round(f1_score(df["intencion"], df["pred"], average="macro"), 4),
        "n_accion": int(len(acc)),
        "exactitud_intenciones_accion": round((acc["pred"] == acc["intencion"]).mean(), 4),
        "exactitud_parametros_accion": round(acc.apply(params_ok, axis=1).mean(), 4),
        "exactitud_por_intencion_accion": (acc["pred"] == acc["intencion"]).groupby(acc["intencion"]).mean().round(3).to_dict(),
        "acciones_falsas_sobre_no_accion": f"{len(falsas)} de {len(no_accion)}",
        "ejemplos_acciones_falsas": falsas[["instruccion", "intencion", "pred"]].head(8).to_dict(orient="records"),
        "ejemplos_errores_accion": acc[acc["pred"] != acc["intencion"]][["instruccion", "intencion", "pred"]].head(8).to_dict(orient="records"),
    }
    return res


def main():
    resultados = {n: evaluar(n) for n in ["test", "test_voz"]}
    with open(REPORTE, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(json.dumps(resultados, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
