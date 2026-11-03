"""
baseline.py
Modelos de referencia (sin LLM) para la clasificación de intenciones y
evaluación del recuperador de ejemplos few-shot.

  - Representación: TF-IDF de n-gramas de caracteres (2-5), robusta a
    faltas de tildes y errores menores de transcripción.
  - B1: vecino más cercano (similitud coseno) -> también es el recuperador
        que selecciona los ejemplos few-shot del prompt del LLM.
  - B2: regresión logística multinomial.

Métricas: exactitud y F1 macro en val, test y test_voz; recall@k del
recuperador (proporción de consultas cuyo top-k contiene al menos un
ejemplo de la intención correcta).

Uso:
    python src/models/baseline.py
"""

import json
import os

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score

SEMILLA = 42
K = 8
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROC = os.path.join(RAIZ, "data", "processed")
REPORTE = os.path.join(RAIZ, "reports", "baseline_resultados.json")


def cargar(nombre):
    return pd.read_json(os.path.join(PROC, f"{nombre}.jsonl"), lines=True)


def main():
    train = cargar("train")
    conjuntos = {n: cargar(n) for n in ["val", "test", "test_voz"]}

    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), lowercase=True,
                          strip_accents="unicode", sublinear_tf=True)
    X_train = vec.fit_transform(train["instruccion"])
    y_train = train["intencion"].values

    logreg = LogisticRegression(max_iter=2000, C=10, random_state=SEMILLA)
    logreg.fit(X_train, y_train)

    resultados = {"k": K, "train": int(len(train)), "vocabulario_ngramas": int(len(vec.vocabulary_))}
    for nombre, df in conjuntos.items():
        X = vec.transform(df["instruccion"])
        y = df["intencion"].values
        sim = (X @ X_train.T).toarray()
        orden = np.argsort(-sim, axis=1)
        pred_knn = y_train[orden[:, 0]]
        topk = y_train[orden[:, :K]]
        recall_k = float(np.mean([y[i] in topk[i] for i in range(len(y))]))
        pred_lr = logreg.predict(X)
        resultados[nombre] = {
            "n": int(len(df)),
            "knn_exactitud": round(accuracy_score(y, pred_knn), 4),
            "knn_f1_macro": round(f1_score(y, pred_knn, average="macro"), 4),
            "logreg_exactitud": round(accuracy_score(y, pred_lr), 4),
            "logreg_f1_macro": round(f1_score(y, pred_lr, average="macro"), 4),
            f"recuperador_recall@{K}": round(recall_k, 4),
        }
        if nombre == "test":
            errores = df.loc[pred_lr != y, ["instruccion", "intencion"]].assign(prediccion=pred_lr[pred_lr != y])
            resultados["errores_logreg_test"] = errores.to_dict(orient="records")

    with open(REPORTE, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(json.dumps(resultados, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
