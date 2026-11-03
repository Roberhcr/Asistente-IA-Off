import os


# ============================================================
# CARPETAS CONOCIDAS (estándar de Windows, no requieren
# configuración manual)
# ============================================================

CARPETAS = {
    "escritorio": "Desktop",
    "descargas": "Downloads",
    "documentos": "Documents",
    "imagenes": "Pictures",
    "imágenes": "Pictures",
    "musica": "Music",
    "música": "Music",
    "videos": "Videos",
}


def abrir_carpeta(nombre):

    nombre = (nombre or "").strip().lower()

    carpeta = CARPETAS.get(nombre)

    if carpeta is None:

        return {
            "ok": False,
            "mensaje": f"No conozco la carpeta \"{nombre}\"."
        }

    ruta = os.path.join(
        os.path.expanduser("~"),
        carpeta
    )

    if not os.path.isdir(ruta):

        return {
            "ok": False,
            "mensaje": f"No encontré la carpeta en:\n{ruta}"
        }

    try:

        os.startfile(ruta)

        return {
            "ok": True,
            "mensaje": f"Abriendo {nombre}."
        }

    except Exception as error:

        return {
            "ok": False,
            "mensaje": f"No pude abrir {nombre}: {error}"
        }