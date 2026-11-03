import re


# ============================================================
# CONFIGURACIÓN
# ============================================================

# Nombre(s) por los que el usuario puede llamar a la IA antes
# de dar el comando. No es obligatorio decirlo (por texto no
# hace falta), pero si lo dice, se lo quitamos del mensaje.
PALABRAS_ACTIVACION = ["oddye"]


VERBOS_ABRIR = [
    "abre", "abra", "ábreme", "abreme", "abrirme",
    "ábrelo", "ábrela", "abrilo", "abrila", "abrir",
    "inicia", "inicie", "iniciar",
    "lanza", "lance", "lanzar",
    "ejecuta", "ejecute", "ejecutar",
    "pon", "ponme", "poner",
    "entra a", "entra en",
   
    
]


PALABRAS_CARPETA = [
    "escritorio",
    "descargas",
    "documentos",
    "imagenes",
    "imágenes",
    "musica",
    "música",
    "videos",
]


RELLENOS = [
    "la carpeta de",
    "la carpeta",
    "el archivo",
    "el programa",
    "la aplicacion",
    "la aplicación",
    "mis",
    "mi",
    "la",
    "el",
]


# Frase (tal como puede decirse) -> nombre de la acción
COMANDOS_SISTEMA = {
    "bloquea la pantalla": "bloquear_pantalla",
    "bloquear pantalla": "bloquear_pantalla",
    "bloquea el equipo": "bloquear_pantalla",

    "silencia el volumen": "silenciar_volumen",
    "silenciar volumen": "silenciar_volumen",
    "activa el volumen": "silenciar_volumen",
    "quita el silencio": "silenciar_volumen",

    "sube el volumen": "subir_volumen",
    "subir volumen": "subir_volumen",
    "mas volumen": "subir_volumen",
    "más volumen": "subir_volumen",

    "baja el volumen": "bajar_volumen",
    "bajar volumen": "bajar_volumen",
    "menos volumen": "bajar_volumen",

    "toma una captura": "captura_pantalla",
    "toma captura": "captura_pantalla",
    "captura de pantalla": "captura_pantalla",
    "capturar pantalla": "captura_pantalla",

    "abre el explorador": "abrir_explorador",
    "abrir explorador": "abrir_explorador",

    "vacia la papelera": "vaciar_papelera",
    "vacía la papelera": "vaciar_papelera",
    "vaciar papelera": "vaciar_papelera",

    "apaga el equipo": "apagar_equipo",
    "apagar equipo": "apagar_equipo",
    "apaga la pc": "apagar_equipo",
    "apaga la computadora": "apagar_equipo",

    "reinicia el equipo": "reiniciar_equipo",
    "reiniciar equipo": "reiniciar_equipo",
    "reinicia la pc": "reiniciar_equipo",

    "cancela el apagado": "cancelar_apagado",
    "cancelar apagado": "cancelar_apagado",
    "cancela el reinicio": "cancelar_apagado",
}


# ============================================================
# UTILIDADES
# ============================================================

def _normalizar(texto):

    texto = texto.strip().lower()

    # quita signos de interrogación/exclamación comunes
    texto = texto.replace("¿", "").replace("?", "")
    texto = texto.replace("¡", "").replace("!", "")

    texto = re.sub(r"\s+", " ", texto)

    return texto


def _quitar_activacion(texto):

    for palabra in PALABRAS_ACTIVACION:

        patron = rf"^{palabra}[,:]?\s+"

        texto = re.sub(patron, "", texto)

    return texto.strip()


def _quitar_rellenos(texto):

    for relleno in RELLENOS:

        patron = rf"^{re.escape(relleno)}\s+"

        nuevo = re.sub(patron, "", texto)

        if nuevo != texto:
            texto = nuevo

    return texto.strip()


# ============================================================
# DETECCIÓN PRINCIPAL
# ============================================================

def detectar_intencion(texto_original):
    """
    Devuelve un diccionario describiendo qué quiere el usuario:

    {"intencion": "sistema", "accion": "bloquear_pantalla"}
    {"intencion": "carpeta", "nombre": "descargas"}
    {"intencion": "programa", "nombre": "spotify"}
    {"intencion": "chat"}   -> no es un comando, seguir a Qwen
    """

    if not texto_original:
        return {"intencion": "chat"}

    texto = _normalizar(texto_original)
    texto = _quitar_activacion(texto)

    # --------------------------------------------------------
    # 1) Comandos de sistema (frase completa contenida)
    # --------------------------------------------------------

    for frase, accion in COMANDOS_SISTEMA.items():

        if frase in texto:

            return {
                "intencion": "sistema",
                "accion": accion
            }


    # --------------------------------------------------------
    # 2) Abrir algo (programa, carpeta o "archivos")
    #    Busca el verbo en cualquier parte de la frase, no
    #    solo al inicio (para frases como "puedes abrir word"
    #    o "que me abra word").
    # --------------------------------------------------------

    verbos_ordenados = sorted(
        VERBOS_ABRIR,
        key=len,
        reverse=True
    )

    for verbo in verbos_ordenados:

        patron = r"\b" + re.escape(verbo) + r"\b\s+(.+)"

        coincidencia = re.search(patron, texto)

        if coincidencia:

            resto = coincidencia.group(1).strip()

            resto = _quitar_rellenos(resto)

            if not resto:
                continue

            if resto in PALABRAS_CARPETA:

                return {
                    "intencion": "carpeta",
                    "nombre": resto
                }

            return {
                "intencion": "programa",
                "nombre": resto
            }


    # --------------------------------------------------------
    # 3) No coincide con ningún comando conocido
    # --------------------------------------------------------

    return {"intencion": "chat"}
