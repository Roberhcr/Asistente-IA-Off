"""
predict_model.py
Intérprete de instrucciones basado en Qwen3-4B (llama-server) con
adaptación por aprendizaje en contexto (few-shot) y salida JSON restringida.

Flujo:
  instrucción -> recuperador TF-IDF (k ejemplos más similares del banco few-shot)
              -> prompt: instrucción de sistema + catálogo + k ejemplos + instrucción
              -> llama-server /v1/chat/completions con JSON Schema (decodificación restringida)
              -> validación contra el esquema de la intención
              -> si no es válido: intención "ambigua" (el asistente pide aclaración)

Requiere llama-server activo en http://127.0.0.1:8080 (lo arranca main.py).

Uso:
    python src/models/predict_model.py "abre la carpeta de descargas"
    python src/models/predict_model.py --evaluar test        # o test_voz / val
"""

import argparse
import json
import os
import time
import urllib.request

import jsonschema
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROC = os.path.join(RAIZ, "data", "processed")
REPORTES = os.path.join(RAIZ, "reports")
LLAMA_URL = "http://127.0.0.1:8080"
K = 8


class Interprete:
    def __init__(self, k=K):
        self.k = k
        with open(os.path.join(PROC, "esquema_salida.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        self.system_prompt = cfg["system_prompt"]
        self.esquemas = cfg["intenciones"]
        self.valores = cfg.get("valores_canonicos", {})
        self.banco = pd.read_json(os.path.join(PROC, "fewshot_bank.jsonl"), lines=True)
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5),
                                   strip_accents="unicode", sublinear_tf=True)
        self.X = self.vec.fit_transform(self.banco["messages"].apply(lambda m: m[0]["content"]))
        # Esquema global: la intención debe pertenecer al catálogo
        self.esquema_global = {
            "type": "object",
            "properties": {"intencion": {"enum": list(self.esquemas)},
                           "parametros": {"type": "object"}},
            "required": ["intencion", "parametros"],
            "additionalProperties": False,
        }

    def _ejemplos(self, texto):
        sim = (self.vec.transform([texto]) @ self.X.T).toarray()[0]
        idx = sim.argsort()[::-1][: self.k]
        mensajes = []
        for i in reversed(idx):  # el más parecido queda más cerca de la consulta
            mensajes.extend(self.banco.iloc[i]["messages"])
        return mensajes

    def _prompt(self, texto, contexto=None):
        catalogo = "\n".join(f"- {k}: {list(v['properties'])}" for k, v in self.esquemas.items())
        valores = "\n".join(f"- {k}: {', '.join(v)}" for k, v in self.valores.items())
        sistema = (f"{self.system_prompt}\nCatálogo (intención: parámetros):\n{catalogo}"
                   f"\nValores canónicos conocidos:\n{valores}")
        usuario = texto if not contexto else f"[Contexto: {contexto}]\n{texto}"
        return [{"role": "system", "content": sistema}] + self._ejemplos(texto) + \
               [{"role": "user", "content": usuario}]

    def interpretar(self, texto, contexto=None):
        datos = {
            "messages": self._prompt(texto, contexto),
            "temperature": 0,
            "max_tokens": 160,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "accion", "schema": self.esquema_global}},
        }
        req = urllib.request.Request(LLAMA_URL + "/v1/chat/completions",
                                     data=json.dumps(datos).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        t0 = time.perf_counter()
        resp = json.loads(urllib.request.urlopen(req, timeout=120).read().decode("utf-8"))
        latencia = time.perf_counter() - t0
        crudo = resp["choices"][0]["message"]["content"]
        try:
            salida = json.loads(crudo)
            jsonschema.validate(salida["parametros"], self.esquemas[salida["intencion"]])
            valido = True
        except Exception:
            salida, valido = {"intencion": "ambigua", "parametros": {}}, False
        return {"salida": salida, "json_valido": valido, "latencia_s": round(latencia, 3), "crudo": crudo}


def evaluar(nombre):
    from sklearn.metrics import accuracy_score, f1_score
    interprete = Interprete()
    df = pd.read_json(os.path.join(PROC, f"{nombre}.jsonl"), lines=True)
    filas = []
    for _, r in df.iterrows():
        ctx = r["contexto"] if isinstance(r["contexto"], str) else None
        res = interprete.interpretar(r["instruccion"], ctx)
        filas.append({
            "id": r["id"], "instruccion": r["instruccion"], "intencion": r["intencion"],
            "prediccion": res["salida"]["intencion"],
            "parametros_ok": res["salida"]["parametros"] == r["parametros"],
            "json_valido": res["json_valido"], "latencia_s": res["latencia_s"],
        })
    out = pd.DataFrame(filas)
    metricas = {
        "conjunto": nombre, "n": int(len(out)), "k": K,
        "exactitud_intencion": round(accuracy_score(out["intencion"], out["prediccion"]), 4),
        "f1_macro": round(f1_score(out["intencion"], out["prediccion"], average="macro"), 4),
        "exactitud_parametros": round(out["parametros_ok"].mean(), 4),
        "json_valido": round(out["json_valido"].mean(), 4),
        "latencia_media_s": round(out["latencia_s"].mean(), 3),
        "latencia_p95_s": round(out["latencia_s"].quantile(0.95), 3),
    }
    out.to_csv(os.path.join(REPORTES, f"llm_predicciones_{nombre}.csv"), index=False, encoding="utf-8")
    with open(os.path.join(REPORTES, f"llm_metricas_{nombre}.json"), "w", encoding="utf-8") as f:
        json.dump(metricas, f, ensure_ascii=False, indent=2)
    print(json.dumps(metricas, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("texto", nargs="?")
    ap.add_argument("--evaluar", choices=["val", "test", "test_voz"])
    args = ap.parse_args()
    if args.evaluar:
        evaluar(args.evaluar)
    elif args.texto:
        print(json.dumps(Interprete().interpretar(args.texto), ensure_ascii=False, indent=1))
    else:
        ap.print_help()
