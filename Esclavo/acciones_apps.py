import os
import subprocess
import webbrowser
import re
import unicodedata


# ============================================================
# CONFIGURACIÓN DE APLICACIONES
# ============================================================

MAPA_APPS = {
    "spotify": {
        "tipo": "aplicacion",
        "ruta": os.path.expandvars(
            r"%APPDATA%\Spotify\Spotify.exe"
        ),
        "proceso": "Spotify.exe",
        "alias": [
            "spotify",
            "spotify music",
        ],
    },

    "word": {
        "tipo": "aplicacion",
        "ruta": (
            r"C:\Program Files\Microsoft Office"
            r"\root\Office16\WINWORD.EXE"
        ),
        "proceso": "WINWORD.EXE",
        "alias": [
            "word",
            "microsoft word",
            "ms word",
            "office word",
            "microsoft office word",
        ],
    },

    "netflix": {
        "tipo": "web",
        "url": "https://www.netflix.com",
        "alias": [
            "netflix",
        ],
    },

    "youtube": {
        "tipo": "web",
        "url": "https://www.youtube.com",
        "alias": [
            "youtube",
            "you tube",
            "you-tube",
            "youtub",
        ],
    },

    "archivos": {
        "tipo": "sistema",
        "alias": [
            "archivos",
            "mis archivos",
            "explorador",
            "explorador de archivos",
            "explorador de windows",
            "windows explorer",
        ],
    },
}


# ============================================================
# CONTEXTO DE APLICACIONES
# ============================================================

# Última aplicación que Oddye identificó/abrió.
ULTIMA_APP = None

# Aplicaciones que Oddye ha abierto durante esta ejecución.
APPS_ABIERTAS = set()


# ============================================================
# PALABRAS QUE NO FORMAN PARTE DEL NOMBRE DE LA APP
# ============================================================

PALABRAS_IGNORAR = {
    "oddye",
    "oye",
    "hey",
    "hola",
    "por",
    "favor",
    "puedes",
    "puede",
    "podrias",
    "podrías",
    "quiero",
    "quisiera",
    "necesito",
    "necesitas",
    "me",
    "te",
    "que",
    "qué",
    "porfa",
    "porfavor",
    "la",
    "el",
    "los",
    "las",
    "una",
    "un",
    "esa",
    "ese",
    "esta",
    "este",
    "aplicacion",
    "aplicación",
    "programa",
    "app",
}


# ============================================================
# ACCIONES
# ============================================================

VERBOS_ABRIR = {
    "abrir",
    "abre",
    "abrime",
    "abrirme",
    "abrirlo",
    "abrirla",
    "iniciar",
    "inicia",
    "iniciame",
    "iniciarme",
    "ejecutar",
    "ejecuta",
    "ejecutame",
    "ejecutarme",
    "lanzar",
    "lanza",
    "lanzame",
    "lanzarme",
    "abrirle",
    "poner",
    "pon",
}

VERBOS_CERRAR = {
    "cerrar",
    "cierra",
    "cierrame",
    "cerrarme",
    "cerrarlo",
    "cerrarla",
    "salir",
    "terminar",
    "termina",
    "finalizar",
    "finaliza",
    "apagar",
    "apaga",
}


# ============================================================
# REFERENCIAS DE CONTEXTO
# ============================================================

REFERENCIAS_ULTIMA_APP = {
    "lo",
    "la",
    "los",
    "las",
    "ello",
    "esa",
    "ese",
    "esta",
    "este",
    "esa app",
    "ese app",
    "esta app",
    "este app",
    "esa aplicacion",
    "esa aplicación",
    "ese programa",
    "la aplicacion",
    "la aplicación",
    "el programa",
    "la app",
}


# ============================================================
# NORMALIZACIÓN DE TEXTO
# ============================================================

def normalizar_texto(texto):
    """
    Normaliza el texto para facilitar la interpretación.

    Ejemplos:

        "  You Tube  "      -> "you tube"
        "¡Microsoft Word!" -> "microsoft word"
        "¿Puedes abrirlo?"  -> "puedes abrirlo"
    """

    if not texto:
        return ""

    texto = str(texto).lower().strip()

    # Eliminar acentos para facilitar coincidencias.
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )

    # Reemplazar signos por espacios.
    texto = re.sub(r"[¿?¡!.,;:()\[\]{}\"']", " ", texto)

    # Normalizar guiones.
    texto = texto.replace("-", " ")

    # Quitar espacios repetidos.
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


# ============================================================
# NORMALIZACIÓN DE NOMBRES DE APLICACIONES
# ============================================================

def normalizar_nombre_app(nombre):
    """
    Convierte diferentes formas de escribir una aplicación
    en su nombre interno.

    Ejemplos:

        "you tube" -> "youtube"
        "you-tube" -> "youtube"
        "microsoft word" -> "word"
        "ms word" -> "word"
    """

    if not nombre:
        return None

    texto = normalizar_texto(nombre)

    # Primero buscamos coincidencia directa con alias.
    for nombre_interno, datos in MAPA_APPS.items():

        for alias in datos.get("alias", []):
            alias_normalizado = normalizar_texto(alias)

            if texto == alias_normalizado:
                return nombre_interno

    # Normalizaciones específicas adicionales.
    equivalencias = {
        "you tube": "youtube",
        "you-tube": "youtube",
        "youtub": "youtube",

        "microsoft word": "word",
        "ms word": "word",
        "office word": "word",
        "microsoft office word": "word",
    }

    if texto in equivalencias:
        return equivalencias[texto]

    return None


# ============================================================
# BUSCAR APLICACIÓN
# ============================================================

def buscar_app(nombre):
    """
    Busca una aplicación por nombre o alias.

    Devuelve:
        (nombre_interno, datos)

    o:
        (None, None)
    """

    if not nombre:
        return None, None

    nombre_normalizado = normalizar_nombre_app(nombre)

    if nombre_normalizado:
        return (
            nombre_normalizado,
            MAPA_APPS[nombre_normalizado]
        )

    # Búsqueda parcial.
    texto = normalizar_texto(nombre)

    for nombre_interno, datos in MAPA_APPS.items():

        if texto == nombre_interno:
            return nombre_interno, datos

        for alias in datos.get("alias", []):

            alias_normalizado = normalizar_texto(alias)

            if alias_normalizado in texto:
                return nombre_interno, datos

    return None, None


# ============================================================
# DETECTAR APLICACIÓN DENTRO DE UNA FRASE
# ============================================================

def detectar_app_en_texto(texto):
    """
    Busca si alguna aplicación conocida aparece dentro de una frase.

    Ejemplos:

        "abre microsoft word" -> "word"
        "ejecuta you tube" -> "youtube"
        "puedes abrir spotify" -> "spotify"
    """

    texto_normalizado = normalizar_texto(texto)

    # Primero buscamos los alias más largos.
    candidatos = []

    for nombre_interno, datos in MAPA_APPS.items():

        for alias in datos.get("alias", []):

            alias_normalizado = normalizar_texto(alias)

            if alias_normalizado:
                candidatos.append(
                    (
                        len(alias_normalizado),
                        nombre_interno,
                        alias_normalizado
                    )
                )

    candidatos.sort(reverse=True)

    for _, nombre_interno, alias_normalizado in candidatos:

        if re.search(
            r"\b" + re.escape(alias_normalizado) + r"\b",
            texto_normalizado
        ):
            return nombre_interno

    return None


# ============================================================
# EXTRAER NOMBRE DE APLICACIÓN
# ============================================================

def extraer_nombre_app(texto):
    """
    Intenta obtener únicamente el nombre de la aplicación
    desde una frase natural.
    """

    if not texto:
        return None

    app = detectar_app_en_texto(texto)

    if app:
        return app

    # Si el texto completo es simplemente un alias.
    app = normalizar_nombre_app(texto)

    if app:
        return app

    return None


# ============================================================
# DETECTAR REFERENCIA AL CONTEXTO
# ============================================================

def es_referencia_a_ultima_app(texto):
    """
    Detecta expresiones como:

        "lo"
        "ciérralo"
        "esa aplicación"
        "ese programa"
        "la app"
    """

    texto_normalizado = normalizar_texto(texto)

    # Caso exacto.
    if texto_normalizado in REFERENCIAS_ULTIMA_APP:
        return True

    # Casos donde aparece dentro de una frase.
    patrones = [
        r"\blo\b",
        r"\bla\b",
        r"\besa aplicacion\b",
        r"\bese programa\b",
        r"\besa app\b",
        r"\beste programa\b",
        r"\besta aplicacion\b",
        r"\bla app\b",
        r"\bel programa\b",
    ]

    for patron in patrones:

        if re.search(patron, texto_normalizado):
            return True

    return False


# ============================================================
# RESOLVER OBJETIVO
# ============================================================

def resolver_objetivo(texto):
    """
    Determina qué aplicación está mencionando el usuario.

    Si no menciona una aplicación explícitamente, intenta
    utilizar la última aplicación conocida.
    """

    global ULTIMA_APP

    app = extraer_nombre_app(texto)

    if app:
        return app

    if es_referencia_a_ultima_app(texto):
        return ULTIMA_APP

    return None


# ============================================================
# INTERPRETAR ACCIÓN
# ============================================================

def interpretar_apertura(texto):
    """
    Interpreta comandos relacionados con abrir o cerrar aplicaciones.

    Devuelve None si no detecta una acción de aplicación.

    Ejemplos:

        "abre word"

        {
            "accion": "abrir_app",
            "nombre": "word"
        }

        "puedes cerrar youtube"

        {
            "accion": "cerrar_app",
            "nombre": "youtube"
        }

        "ciérralo"

        {
            "accion": "cerrar_app",
            "nombre": "youtube",
            "origen": "contexto"
        }
    """

    if not texto:
        return None

    texto_normalizado = normalizar_texto(texto)

    palabras = set(texto_normalizado.split())

    # --------------------------------------------------------
    # 1. Detectar aplicación explícita
    # --------------------------------------------------------

    app = extraer_nombre_app(texto)

    # --------------------------------------------------------
    # 2. Detectar acción de abrir
    # --------------------------------------------------------

    tiene_accion_abrir = False

    for verbo in VERBOS_ABRIR:

        verbo_normalizado = normalizar_texto(verbo)

        if re.search(
            r"\b" + re.escape(verbo_normalizado) + r"\b",
            texto_normalizado
        ):
            tiene_accion_abrir = True
            break

    if tiene_accion_abrir:

        if app:

            return {
                "accion": "abrir_app",
                "nombre": app,
                "origen": "texto",
            }

        # Ejemplo:
        # "puedes abrirlo"
        objetivo = resolver_objetivo(texto)

        if objetivo:

            return {
                "accion": "abrir_app",
                "nombre": objetivo,
                "origen": "contexto",
            }

        return None

    # --------------------------------------------------------
    # 3. Detectar acción de cerrar
    # --------------------------------------------------------

    tiene_accion_cerrar = False

    for verbo in VERBOS_CERRAR:

        verbo_normalizado = normalizar_texto(verbo)

        if re.search(
            r"\b" + re.escape(verbo_normalizado) + r"\b",
            texto_normalizado
        ):
            tiene_accion_cerrar = True
            break

    if tiene_accion_cerrar:

        if app:

            return {
                "accion": "cerrar_app",
                "nombre": app,
                "origen": "texto",
            }

        # "ciérralo", "cierra esa app", etc.
        objetivo = resolver_objetivo(texto)

        if objetivo:

            return {
                "accion": "cerrar_app",
                "nombre": objetivo,
                "origen": "contexto",
            }

        return None

    # --------------------------------------------------------
    # 4. Si solamente dice el nombre de una app conocida
    # --------------------------------------------------------

    texto_como_app = normalizar_nombre_app(texto)

    if texto_como_app:

        return {
            "accion": "abrir_app",
            "nombre": texto_como_app,
            "origen": "nombre_directo",
        }

    return None


# ============================================================
# ABRIR APLICACIÓN
# ============================================================

def abrir_app(nombre, observador=None):
    """
    Abre una aplicación registrada.

    Conserva el sistema de ObservadorPC utilizado por Oddye.
    """

    global ULTIMA_APP

    nombre_normalizado = normalizar_nombre_app(nombre)

    if not nombre_normalizado:

        return {
            "ok": False,
            "respuesta": (
                f'No tengo registrada ninguna app llamada "{nombre}". '
                "Puedes agregarla en Esclavo/acciones_apps.py."
            ),
        }

    nombre = nombre_normalizado

    datos = MAPA_APPS.get(nombre)

    if not datos:

        return {
            "ok": False,
            "respuesta": (
                f'No tengo registrada ninguna app llamada "{nombre}".'
            ),
        }

    nombre_bonito = nombre.capitalize()

    tipo = datos.get("tipo")

    # --------------------------------------------------------
    # APLICACIÓN WEB
    # --------------------------------------------------------

    if tipo == "web":

        try:

            webbrowser.open(datos["url"])

            ULTIMA_APP = nombre
            APPS_ABIERTAS.add(nombre)

            return {
                "ok": True,
                "respuesta": f"{nombre_bonito} se abrió correctamente.",
            }

        except Exception as e:

            return {
                "ok": False,
                "respuesta": (
                    f"No pude abrir {nombre_bonito}: {e}"
                ),
            }

    # --------------------------------------------------------
    # SISTEMA / EXPLORADOR
    # --------------------------------------------------------

    if tipo == "sistema":

        try:

            os.startfile(os.path.expanduser("~"))

            ULTIMA_APP = nombre
            APPS_ABIERTAS.add(nombre)

            return {
                "ok": True,
                "respuesta": (
                    f"{nombre_bonito} se abrió correctamente."
                ),
            }

        except Exception as e:

            return {
                "ok": False,
                "respuesta": (
                    f"No pude abrir {nombre_bonito}: {e}"
                ),
            }

    # --------------------------------------------------------
    # APLICACIÓN NORMAL DE WINDOWS
    # --------------------------------------------------------

    ruta = datos.get("ruta")

    if not ruta:

        return {
            "ok": False,
            "respuesta": (
                f"No tengo una ruta configurada para {nombre_bonito}."
            ),
        }

    if not os.path.exists(ruta):

        return {
            "ok": False,
            "respuesta": (
                f"No encontré {nombre_bonito} en la ruta configurada."
            ),
        }

    try:

        subprocess.Popen([ruta])

        ULTIMA_APP = nombre
        APPS_ABIERTAS.add(nombre)

        # ----------------------------------------------------
        # OBSERVADOR DE APERTURA
        # ----------------------------------------------------

        if observador:

            proceso = datos.get("proceso")

            if proceso:

                comprobacion = observador.comprobar_apertura(
                    nombre_bonito,
                    proceso
                )

                if comprobacion.get("ok"):

                    return {
                        "ok": True,
                        "respuesta": (
                            f"{nombre_bonito} se abrió correctamente."
                        ),
                        "patron": comprobacion.get("patron"),
                    }

                return {
                    "ok": False,
                    "respuesta": (
                        f"Intenté abrir {nombre_bonito}, "
                        "pero no pude confirmar que se iniciara."
                    ),
                    "patron": comprobacion.get("patron"),
                }

        return {
            "ok": True,
            "respuesta": f"{nombre_bonito} se abrió correctamente.",
        }

    except Exception as e:

        return {
            "ok": False,
            "respuesta": (
                f"No pude abrir {nombre_bonito}: {e}"
            ),
        }


# ============================================================
# CERRAR APLICACIÓN
# ============================================================

def cerrar_app(nombre):
    """
    Cierra una aplicación registrada.

    Se utiliza el nombre del proceso configurado en MAPA_APPS.

    Ejemplos:

        cerrar_app("word")
        cerrar_app("youtube")
        cerrar_app("spotify")
    """

    global ULTIMA_APP

    nombre_normalizado = normalizar_nombre_app(nombre)

    if not nombre_normalizado:

        return {
            "ok": False,
            "respuesta": (
                f'No conozco ninguna aplicación llamada "{nombre}".'
            ),
        }

    nombre = nombre_normalizado

    datos = MAPA_APPS.get(nombre)

    if not datos:

        return {
            "ok": False,
            "respuesta": (
                f'No tengo registrada ninguna app llamada "{nombre}".'
            ),
        }

    nombre_bonito = nombre.capitalize()

    tipo = datos.get("tipo")

    # --------------------------------------------------------
    # PÁGINAS WEB
    # --------------------------------------------------------
    #
    # Una página web no se puede cerrar de forma segura
    # solamente con webbrowser.
    #
    # Por ahora informamos al usuario.
    #

    if tipo == "web":

        return {
            "ok": False,
            "respuesta": (
                f"{nombre_bonito} está abierto en el navegador. "
                "El cierre del navegador lo implementaremos "
                "en la siguiente capa de control de ventanas."
            ),
        }

    # --------------------------------------------------------
    # APLICACIÓN DEL SISTEMA
    # --------------------------------------------------------

    if tipo == "sistema":

        proceso = datos.get("proceso")

        if not proceso:

            return {
                "ok": False,
                "respuesta": (
                    f"No tengo configurado el proceso de "
                    f"{nombre_bonito}."
                ),
            }

    # --------------------------------------------------------
    # OBTENER PROCESO
    # --------------------------------------------------------

    proceso = datos.get("proceso")

    if not proceso:

        return {
            "ok": False,
            "respuesta": (
                f"No tengo configurado el proceso de "
                f"{nombre_bonito}."
            ),
        }

    # --------------------------------------------------------
    # CERRAR PROCESO
    # --------------------------------------------------------

    try:

        resultado = subprocess.run(
            [
                "taskkill",
                "/IM",
                proceso,
                "/T",
            ],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        if resultado.returncode == 0:

            APPS_ABIERTAS.discard(nombre)

            if ULTIMA_APP == nombre:
                ULTIMA_APP = None

            return {
                "ok": True,
                "respuesta": (
                    f"{nombre_bonito} se cerró correctamente."
                ),
            }

        # ----------------------------------------------------
        # SI NO ESTABA ABIERTA
        # ----------------------------------------------------

        salida = (
            (resultado.stdout or "") +
            (resultado.stderr or "")
        ).lower()

        if (
            "not found" in salida
            or "no se encontró" in salida
            or "no se encontro" in salida
            or "no running" in salida
        ):

            return {
                "ok": False,
                "respuesta": (
                    f"{nombre_bonito} no parece estar abierto."
                ),
            }

        return {
            "ok": False,
            "respuesta": (
                f"No pude cerrar {nombre_bonito}."
            ),
        }

    except Exception as e:

        return {
            "ok": False,
            "respuesta": (
                f"No pude cerrar {nombre_bonito}: {e}"
            ),
        }


# ============================================================
# OBTENER CONTEXTO ACTUAL
# ============================================================

def obtener_contexto():
    """
    Devuelve información sencilla sobre el contexto actual.
    """

    return {
        "ultima_app": ULTIMA_APP,
        "apps_abiertas": list(APPS_ABIERTAS),
    }


# ============================================================
# LIMPIAR CONTEXTO
# ============================================================

def limpiar_contexto():
    """
    Limpia el contexto temporal de aplicaciones.
    """

    global ULTIMA_APP

    ULTIMA_APP = None
    APPS_ABIERTAS.clear()