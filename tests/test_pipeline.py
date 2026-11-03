"""Pruebas básicas del pipeline de datos y del intérprete (sin necesidad del LLM)."""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import jsonschema  # noqa: E402
from src.features.build_features import clave, variante_voz, esquema_de  # noqa: E402
from src.models.predict_model import Interprete  # noqa: E402

PROC = os.path.join(RAIZ, "data", "processed")


def leer(nombre):
    with open(os.path.join(PROC, f"{nombre}.jsonl"), encoding="utf-8") as f:
        return [json.loads(l) for l in f]


def test_clave_ignora_tildes_mayusculas_y_signos():
    assert clave("¿Qué estaba haciendo?") == clave("que estaba haciendo")


def test_variante_voz_conserva_enie():
    assert variante_voz("Ábreme el año, ¿sí?") == "abreme el año si"


def test_todas_las_salidas_cumplen_su_esquema():
    for nombre in ["train", "val", "test", "test_voz"]:
        for r in leer(nombre):
            salida = json.loads(r["salida_esperada"])
            jsonschema.validate(salida["parametros"], esquema_de(salida["intencion"]))


def test_sin_fuga_entre_particiones():
    def claves(n):
        return {clave(r["instruccion"]) for r in leer(n)}
    tr, va, te = claves("train"), claves("val"), claves("test")
    assert not (tr & te) and not (tr & va) and not (va & te)


def test_prompt_incluye_k_ejemplos_y_consulta_al_final():
    it = Interprete(k=8)
    msgs = it._prompt("abre la carpeta de descargas")
    assert msgs[0]["role"] == "system"
    assert len(msgs) == 1 + 2 * 8 + 1
    assert msgs[-1] == {"role": "user", "content": "abre la carpeta de descargas"}
