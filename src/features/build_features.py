"""
build_features.py
Preprocesamiento del dataset de instrucciones.

Pasos:
  1. Carga de data/raw/ (dataset_v0 + complemento_v1). Los crudos no se modifican.
  2. Normalización del texto (Unicode NFC, espacios, comillas).
  3. Validación de cada registro contra el esquema JSON de su intención.
  4. Deduplicación por clave normalizada (minúsculas, sin tildes ni puntuación)
     y detección de conflictos (misma instrucción con intenciones distintas).
  5. Partición estratificada por intención 70/15/15 con semilla fija.
  6. Variantes "tipo transcripción de voz" (sin mayúsculas, tildes ni signos),
     generadas DENTRO de cada partición para evitar fuga de información.
  7. Exportación a data/processed/ en dos formatos:
       - registros planos (train/val/test/test_voz .jsonl)
       - formato de chat para el banco de ejemplos few-shot (fewshot_bank.jsonl)

Uso:
    python src/features/build_features.py
"""

import json
import os
import random
import re
import unicodedata

import jsonschema
import pandas as pd
from sklearn.model_selection import train_test_split

SEMILLA = 42
PROPORCION_VARIANTES = 0.30

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CRUDOS = [os.path.join(RAIZ, "data", "raw", "dataset_v0.jsonl"),
          os.path.join(RAIZ, "data", "raw", "complemento_v1.jsonl")]
SALIDA = os.path.join(RAIZ, "data", "processed")
REPORTE = os.path.join(RAIZ, "reports", "preprocesamiento_resumen.json")

# ------------------------------------------------------------------
# Esquema de la salida estructurada por intención
# ------------------------------------------------------------------
NULO_O = lambda t: {"type": [t, "null"]}
ESQUEMAS = {
    "abrir_aplicacion": {"aplicacion": {"type": "string"}},
    "cerrar_aplicacion": {"aplicacion": {"type": "string"}},
    "abrir_carpeta": {"carpeta": {"type": "string"}},
    "abrir_archivo": {"nombre": {"type": "string"}, "extension": NULO_O("string")},
    "buscar_archivo": {"consulta": {"type": "string"}, "extension": NULO_O("string")},
    "ejecutar_comando": {"comando": {"type": "string"}, "requiere_confirmacion": {"type": "boolean"}},
    "crear_rutina": {"nombre": {"type": "string"},
                     "acciones": {"type": "array", "minItems": 1, "items": {"type": "object",
                                  "required": ["intencion", "parametros"]}}},
    "ejecutar_rutina": {"nombre": {"type": "string"}},
    "consultar_contexto": {"rango_tiempo": {"enum": ["reciente", "hoy", "ultima_hora"]}},
    "continuar_actividad": {},
    "consultar_historial": {"fecha": {"type": "string"}, "aplicacion": NULO_O("string")},
    "responder_sugerencia": {"respuesta": {"enum": ["aceptar", "rechazar", "posponer"]}},
    "conversacion_general": {},
    "ambigua": {},
    "fuera_de_alcance": {},
}


def esquema_de(intencion):
    props = ESQUEMAS[intencion]
    return {"type": "object", "properties": props, "required": list(props),
            "additionalProperties": False}


SYSTEM_PROMPT = (
    "Eres el intérprete de instrucciones de un asistente de escritorio local. "
    "Devuelve SOLO un objeto JSON con las claves 'intencion' y 'parametros', "
    "usando únicamente las intenciones del catálogo."
)


def normalizar_texto(t):
    t = unicodedata.normalize("NFC", t)
    t = t.replace("“", '"').replace("”", '"').replace("’", "'")
    return re.sub(r"\s+", " ", t).strip()


def clave(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def variante_voz(t):
    """Simula la salida típica de una transcripción: sin mayúsculas, tildes ni signos."""
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn" or c == "̃")  # conserva la ñ
    t = unicodedata.normalize("NFC", t)
    t = re.sub(r"[¿?¡!,.:;\"]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def limpio(v):
    """Convierte NaN de pandas en None para exportar JSON válido."""
    return None if isinstance(v, float) and v != v else v


def salida_esperada(r):
    return json.dumps({"intencion": r["intencion"], "parametros": r["parametros"]}, ensure_ascii=False)


def main():
    random.seed(SEMILLA)
    df = pd.concat([pd.read_json(p, lines=True) for p in CRUDOS], ignore_index=True)
    df["parametros"] = df["parametros"].apply(lambda p: p if isinstance(p, dict) else {})
    reporte = {"registros_crudos": int(len(df)),
               "crudos_por_archivo": {os.path.basename(p): sum(1 for _ in open(p, encoding="utf-8")) for p in CRUDOS}}

    # 2. Normalización
    antes = df["instruccion"].copy()
    df["instruccion"] = df["instruccion"].apply(normalizar_texto)
    reporte["textos_modificados_por_normalizacion"] = int((antes != df["instruccion"]).sum())

    # 3. Validación de esquema
    invalidos = []
    for idx, r in df.iterrows():
        if r["intencion"] not in ESQUEMAS:
            invalidos.append((r["id"], "intención fuera del catálogo"))
            continue
        try:
            jsonschema.validate(r["parametros"], esquema_de(r["intencion"]))
        except jsonschema.ValidationError as e:
            invalidos.append((r["id"], e.message))
    reporte["registros_invalidos"] = len(invalidos)
    reporte["detalle_invalidos"] = invalidos[:20]
    df = df[~df["id"].isin([i for i, _ in invalidos])]

    # 4. Deduplicación y conflictos
    df["clave"] = df["instruccion"].apply(clave)
    conflictos = df.groupby("clave")["intencion"].nunique()
    claves_conflicto = conflictos[conflictos > 1].index.tolist()
    reporte["claves_en_conflicto"] = claves_conflicto
    df = df[~df["clave"].isin(claves_conflicto)]
    n_antes = len(df)
    df = df.drop_duplicates(subset=["clave"], keep="first").reset_index(drop=True)
    reporte["duplicados_eliminados"] = int(n_antes - len(df))
    reporte["registros_unicos"] = int(len(df))
    reporte["unicos_por_intencion"] = df["intencion"].value_counts().to_dict()

    # 5. Partición estratificada 70/15/15
    train, temp = train_test_split(df, test_size=0.30, stratify=df["intencion"], random_state=SEMILLA)
    val, test = train_test_split(temp, test_size=0.50, stratify=temp["intencion"], random_state=SEMILLA)
    particiones = {"train": train, "val": val, "test": test}

    # 6. Variantes tipo voz dentro de cada partición
    def generar_variantes(part, frac):
        filas = []
        for _, r in part.sample(frac=frac, random_state=SEMILLA).iterrows():
            v = variante_voz(r["instruccion"])
            if v != r["instruccion"]:
                nueva = r.copy()
                nueva["id"] = r["id"] + "-voz"
                nueva["instruccion"] = v
                nueva["origen"] = "variante_voz"
                filas.append(nueva)
        return pd.DataFrame(filas)

    var_train = generar_variantes(train, PROPORCION_VARIANTES)  # aumento parcial del banco few-shot
    test_voz = generar_variantes(test, 1.0)  # versión "hablada" de todo el test (prueba de robustez)
    train_aum = pd.concat([train, var_train], ignore_index=True).sample(frac=1, random_state=SEMILLA)

    # 7. Exportación
    os.makedirs(SALIDA, exist_ok=True)
    columnas = ["id", "instruccion", "contexto", "intencion", "parametros", "categoria",
                "requerimiento", "registro", "origen"]

    def exportar(part, nombre):
        ruta = os.path.join(SALIDA, f"{nombre}.jsonl")
        with open(ruta, "w", encoding="utf-8") as f:
            for _, r in part.iterrows():
                fila = {c: limpio(r[c]) for c in columnas}
                fila["salida_esperada"] = salida_esperada(r)
                f.write(json.dumps(fila, ensure_ascii=False) + "\n")
        return len(part)

    tamanos = {
        "train": exportar(train_aum, "train"),
        "val": exportar(val, "val"),
        "test": exportar(test, "test"),
        "test_voz": exportar(test_voz, "test_voz"),
    }

    # Banco few-shot en formato de chat (solo train)
    with open(os.path.join(SALIDA, "fewshot_bank.jsonl"), "w", encoding="utf-8") as f:
        for _, r in train_aum.iterrows():
            usuario = r["instruccion"] if limpio(r["contexto"]) is None else \
                f"[Contexto: {r['contexto']}]\n{r['instruccion']}"
            f.write(json.dumps({"id": r["id"], "intencion": r["intencion"], "messages": [
                {"role": "user", "content": usuario},
                {"role": "assistant", "content": salida_esperada(r)}]}, ensure_ascii=False) + "\n")

    # Valores canónicos observados en train para parámetros de vocabulario cerrado
    valores = {}
    for clave_p in ["aplicacion", "carpeta", "comando", "nombre_rutina"]:
        vistos = set()
        for _, r in train.iterrows():
            p = r["parametros"]
            if clave_p == "nombre_rutina" and r["intencion"] in ("crear_rutina", "ejecutar_rutina"):
                vistos.add(p["nombre"])
            elif clave_p in p and p[clave_p]:
                vistos.add(p[clave_p])
        valores[clave_p] = sorted(vistos)

    with open(os.path.join(SALIDA, "esquema_salida.json"), "w", encoding="utf-8") as f:
        json.dump({"system_prompt": SYSTEM_PROMPT, "valores_canonicos": valores,
                   "intenciones": {k: esquema_de(k) for k in ESQUEMAS}}, f, ensure_ascii=False, indent=2)

    reporte["tamanos_particiones"] = tamanos
    reporte["variantes_voz_train"] = int(len(var_train))
    reporte["particion_por_intencion"] = pd.DataFrame({
        "train": train["intencion"].value_counts(), "val": val["intencion"].value_counts(),
        "test": test["intencion"].value_counts()}).fillna(0).astype(int).to_dict(orient="index")
    reporte["semilla"] = SEMILLA
    with open(REPORTE, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(reporte, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
