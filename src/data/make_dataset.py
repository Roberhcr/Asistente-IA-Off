"""
make_dataset.py
Genera el dataset v0 (crudo) de instrucciones para el asistente de escritorio.

Cada registro relaciona una instrucción en lenguaje natural con la intención
y los parámetros que el asistente debe producir como salida estructurada.

Fuentes de los ejemplos:
  - "plantilla": combinaciones de plantillas lingüísticas y valores de parámetros.
  - "redactado": ejemplos escritos uno a uno por el equipo (frases más naturales,
    coloquiales y con voseo nicaragüense).

Salida: data/raw/dataset_v0.jsonl  (NO se modifica después; el procesamiento
escribe en data/processed/).

Uso:
    python src/data/make_dataset.py
"""

import json
import os
import random

SEMILLA = 42
random.seed(SEMILLA)

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SALIDA = os.path.join(RAIZ, "data", "raw", "dataset_v0.jsonl")

# ------------------------------------------------------------------
# Catálogo de intenciones -> categoría funcional y requerimiento (RF)
# ------------------------------------------------------------------
CATALOGO = {
    "abrir_aplicacion":     ("sistema", "RF-06"),
    "cerrar_aplicacion":    ("sistema", "RF-06"),
    "abrir_carpeta":        ("archivos", "RF-06"),
    "abrir_archivo":        ("archivos", "RF-06"),
    "buscar_archivo":       ("archivos", "RF-06"),
    "ejecutar_comando":     ("sistema", "RF-05"),
    "crear_rutina":         ("automatizacion", "RF-15"),
    "ejecutar_rutina":      ("automatizacion", "RF-15"),
    "consultar_contexto":   ("memoria", "RF-13"),
    "continuar_actividad":  ("memoria", "RF-14"),
    "consultar_historial":  ("memoria", "RF-10"),
    "responder_sugerencia": ("personalizacion", "RF-17"),
    "conversacion_general": ("conversacion", "RF-03"),
    "ambigua":              ("control", "RF-08"),
    "fuera_de_alcance":     ("control", "RF-08"),
}

# ------------------------------------------------------------------
# Valores de parámetros
# ------------------------------------------------------------------
APPS = {
    "navegador": ["el navegador", "Chrome", "Google Chrome", "el Edge", "internet"],
    "word": ["Word", "el Word", "Microsoft Word"],
    "excel": ["Excel", "el Excel"],
    "powerpoint": ["PowerPoint", "el PowerPoint"],
    "spotify": ["Spotify", "la música en Spotify"],
    "vscode": ["Visual Studio Code", "VS Code", "el editor de código"],
    "calculadora": ["la calculadora"],
    "bloc_de_notas": ["el bloc de notas", "el Notepad"],
    "archivos": ["el explorador de archivos", "el explorador", "mis archivos"],
    "youtube": ["YouTube", "el YouTube"],
    "netflix": ["Netflix", "el Netflix"],
    "whatsapp": ["WhatsApp", "el WhatsApp"],
    "teams": ["Teams", "Microsoft Teams"],
    "zoom": ["Zoom", "el Zoom"],
    "configuracion": ["la configuración", "los ajustes del sistema"],
    "terminal": ["la terminal", "la consola", "el CMD"],
}

# Claves idénticas a Esclavo/acciones_carpetas.py (CARPETAS)
CARPETAS = {
    "documentos": ["Documentos", "mis documentos"],
    "descargas": ["Descargas", "las descargas"],
    "escritorio": ["el Escritorio"],
    "imagenes": ["Imágenes", "mis imágenes"],
    "musica": ["Música", "mi música"],
    "videos": ["Videos", "mis videos"],
}

ARCHIVOS = [
    ("informe de inteligencia artificial", "docx"),
    ("tarea de redes", "docx"),
    ("presentación final", "pptx"),
    ("horario de clases", "pdf"),
    ("currículum", "pdf"),
    ("presupuesto del mes", "xlsx"),
    ("notas de la reunión", "txt"),
    ("guía del proyecto", "docx"),
    ("planilla de asistencia", "xlsx"),
    ("apuntes de base de datos", "pdf"),
]

BUSQUEDAS = [
    ("redes", "pdf"), ("factura", "pdf"), ("foto del carnet", "jpg"),
    ("informe", "docx"), ("presupuesto", "xlsx"), ("diapositivas de IA", "pptx"),
    ("contrato", None), ("tarea de cálculo", None), ("captura de pantalla", "png"),
    ("proyecto final", None),
]
EXT_NOMBRE = {"pdf": "el PDF", "docx": "el Word", "xlsx": "el Excel", "pptx": "la presentación",
              "jpg": "la imagen", "png": "la imagen"}

# Claves idénticas a Esclavo/acciones_sistema.py (ACCIONES_SISTEMA).
# "abrir_explorador" no se incluye porque el explorador ya es una aplicación
# ("archivos") y el módulo de aplicaciones la atiende primero.
COMANDOS = {
    "bloquear_pantalla": ["bloquea la pantalla", "bloquea la computadora", "bloquea el equipo"],
    "silenciar_volumen": ["silencia el volumen", "quita el sonido", "mutea la compu"],
    "subir_volumen": ["sube el volumen", "ponle más volumen", "más volumen"],
    "bajar_volumen": ["baja el volumen", "bajale al volumen", "menos volumen"],
    "captura_pantalla": ["toma una captura de pantalla", "haz un screenshot", "captura la pantalla"],
    "vaciar_papelera": ["vacía la papelera", "limpia la papelera de reciclaje"],
    "apagar_equipo": ["apaga la computadora", "apaga el equipo", "apaga la pc"],
    "reiniciar_equipo": ["reinicia la computadora", "reinicia el equipo", "reinicia la pc"],
    "cancelar_apagado": ["cancela el apagado", "no apagues la compu", "cancela el reinicio"],
}
COMANDOS_CRITICOS = {"apagar_equipo", "reiniciar_equipo", "vaciar_papelera"}

RUTINAS = ["estudio", "trabajo", "programación", "mañana", "reunión", "entretenimiento"]

PREFIJOS = ["", "", "", "por favor ", "oye, ", "asistente, ", "porfa ", "ey, "]
SUFIJOS = ["", "", "", " por favor", " porfa", " ahora", " ya"]


def cortesia(frase):
    """Agrega prefijos/sufijos de cortesía de forma aleatoria."""
    prefijo = random.choice(PREFIJOS)
    sufijo = "" if frase.endswith("?") else random.choice(SUFIJOS)
    if prefijo.strip() in ("por favor", "porfa") and sufijo.strip() in ("por favor", "porfa"):
        sufijo = ""  # evita doble cortesía
    texto = prefijo + frase + sufijo
    return texto.strip()


# Verbos según registro: tú, usted, voseo, perífrasis
VERBOS_ABRIR = {
    "tu": ["abre", "ábreme", "inicia", "ejecuta", "pon"],
    "usted": ["abra", "inicie"],
    "vos": ["abrí", "abrime", "iniciá", "poné"],
    "perifrasis": ["quiero abrir", "necesito abrir", "puedes abrir", "me abres", "podrías abrir"],
}
VERBOS_BUSCAR = {
    "tu": ["busca", "encuentra", "búscame"],
    "usted": ["busque", "encuentre"],
    "vos": ["buscá", "buscame", "encontrá"],
    "perifrasis": ["quiero buscar", "necesito encontrar", "puedes buscar", "ayúdame a encontrar"],
}

# Para archivos y carpetas no se usan verbos de "ejecutar/iniciar"
VERBOS_ABRIR_RECURSO = {
    "tu": ["abre", "ábreme", "muéstrame", "enséñame"],
    "usted": ["abra", "muéstreme"],
    "vos": ["abrí", "abrime", "mostrame"],
    "perifrasis": ["quiero abrir", "necesito abrir", "puedes abrir", "me abres", "quiero ver"],
}

REGISTROS = list(VERBOS_ABRIR.keys())


def registro_aleatorio():
    return random.choice(REGISTROS)


registros = []


def agregar(instruccion, intencion, parametros, origen, registro="tu", contexto=None):
    categoria, rf = CATALOGO[intencion]
    registros.append({
        "instruccion": instruccion,
        "contexto": contexto,
        "intencion": intencion,
        "parametros": parametros,
        "categoria": categoria,
        "requerimiento": rf,
        "registro": registro,
        "origen": origen,
    })


# ------------------------------------------------------------------
# 1) Ejemplos generados por plantilla
# ------------------------------------------------------------------
def gen_abrir_aplicacion(n):
    for _ in range(n):
        app = random.choice(list(APPS))
        reg = registro_aleatorio()
        verbo = random.choice(VERBOS_ABRIR[reg])
        frase = f"{verbo} {random.choice(APPS[app])}"
        agregar(cortesia(frase), "abrir_aplicacion", {"aplicacion": app}, "plantilla", reg)


VERBOS_CERRAR = {
    "tu": ["cierra", "ciérrame", "termina", "quita"],
    "usted": ["cierre", "termine"],
    "vos": ["cerrá", "cerrame"],
    "perifrasis": ["quiero cerrar", "puedes cerrar", "necesito cerrar", "me cierras"],
}


def gen_cerrar_aplicacion(n):
    for _ in range(n):
        app = random.choice(list(APPS))
        if random.random() < 0.15:
            # Referencia a la última aplicación abierta (depende del contexto)
            frase = random.choice(["ciérralo", "ciérrala", "cierra esa app", "cerralo", "quítalo", "cierra ese programa"])
            agregar(cortesia(frase), "cerrar_aplicacion", {"aplicacion": app}, "plantilla",
                    "vos" if frase == "cerralo" else "tu",
                    contexto=f"Última aplicación abierta: {app}")
            continue
        reg = registro_aleatorio()
        verbo = random.choice(VERBOS_CERRAR[reg])
        agregar(cortesia(f"{verbo} {random.choice(APPS[app])}"), "cerrar_aplicacion",
                {"aplicacion": app}, "plantilla", reg)


def gen_abrir_carpeta(n):
    for _ in range(n):
        c = random.choice(list(CARPETAS))
        reg = registro_aleatorio()
        verbo = random.choice(VERBOS_ABRIR_RECURSO[reg])
        nombre = random.choice(CARPETAS[c])
        if not nombre.startswith(("la carpeta", "el ", "mis ", "las ")):
            nombre = random.choice(["la carpeta ", "la carpeta de ", ""]) + nombre
        agregar(cortesia(f"{verbo} {nombre}"), "abrir_carpeta", {"carpeta": c}, "plantilla", reg)


def gen_abrir_archivo(n):
    for _ in range(n):
        nombre, ext = random.choice(ARCHIVOS)
        reg = registro_aleatorio()
        verbo = random.choice(VERBOS_ABRIR_RECURSO[reg])
        art = random.choice(["el archivo del ", "el documento del ", "el ", "mi "])
        if nombre.startswith(("presentación", "tarea", "guía", "planilla", "factura")):
            art = random.choice(["la ", "mi ", "el archivo de la "])
        if nombre.startswith(("notas", "apuntes")):
            art = random.choice(["las ", "mis "])
        agregar(cortesia(f"{verbo} {art}{nombre}"), "abrir_archivo",
                {"nombre": nombre, "extension": ext}, "plantilla", reg)


def gen_buscar_archivo(n):
    for _ in range(n):
        consulta, ext = random.choice(BUSQUEDAS)
        reg = registro_aleatorio()
        verbo = random.choice(VERBOS_BUSCAR[reg])
        if ext and random.random() < 0.6:
            frase = f"{verbo} {EXT_NOMBRE[ext]} de {consulta}"
        else:
            frase = f"{verbo} {random.choice(['el archivo de', 'algo que diga', 'los archivos de', 'dónde está lo de'])} {consulta}"
            ext = None
        agregar(cortesia(frase), "buscar_archivo", {"consulta": consulta, "extension": ext},
                "plantilla", reg)


def gen_ejecutar_comando(n):
    for _ in range(n):
        cmd = random.choice(list(COMANDOS))
        frase = random.choice(COMANDOS[cmd])
        agregar(cortesia(frase), "ejecutar_comando",
                {"comando": cmd, "requiere_confirmacion": cmd in COMANDOS_CRITICOS},
                "plantilla", "tu")


def gen_crear_rutina(n):
    for _ in range(n):
        rutina = random.choice(RUTINAS)
        apps = random.sample(list(APPS), k=random.choice([2, 2, 3]))
        nombres = [random.choice(APPS[a]) for a in apps]
        lista = ", ".join(nombres[:-1]) + " y " + nombres[-1]
        plantilla = random.choice([
            "crea una rutina de {r} que abra {l}",
            "configura mi rutina de {r} con {l}",
            "quiero una rutina de {r}: {l}",
            "armá una rutina de {r} que abra {l}",
            "guarda como rutina de {r} abrir {l}",
        ])
        reg = "vos" if plantilla.startswith("armá") else "tu"
        agregar(cortesia(plantilla.format(r=rutina, l=lista)), "crear_rutina",
                {"nombre": rutina, "acciones": [{"intencion": "abrir_aplicacion",
                                                 "parametros": {"aplicacion": a}} for a in apps]},
                "plantilla", reg)


def gen_ejecutar_rutina(n):
    for _ in range(n):
        rutina = random.choice(RUTINAS)
        plantilla = random.choice([
            "inicia mi rutina de {r}", "ejecuta la rutina de {r}", "activa el modo {r}",
            "empezá la rutina de {r}", "prepara todo para {r}", "pon mi rutina de {r}",
            "quiero empezar mi rutina de {r}",
        ])
        reg = "vos" if plantilla.startswith("empezá") else "tu"
        agregar(cortesia(plantilla.format(r=rutina)), "ejecutar_rutina",
                {"nombre": rutina}, "plantilla", reg)


def gen_consultar_historial(n):
    fechas = {"ayer": "ayer", "hoy": "hoy", "esta_semana": "esta semana",
              "lunes": "el lunes", "semana_pasada": "la semana pasada"}
    for _ in range(n):
        f = random.choice(list(fechas))
        plantilla = random.choice([
            "qué abrí {f}", "qué programas usé {f}", "qué archivos abrí {f}",
            "muéstrame mi historial de {f}", "cuántas veces usé Word {f}",
            "qué hice {f} en la compu",
        ])
        recurso = "word" if "Word" in plantilla else None
        texto = plantilla.format(f=fechas[f])
        if random.random() < 0.5 and not texto.startswith("muéstrame"):
            texto = "¿" + texto + "?"
        agregar(cortesia(texto),
                "consultar_historial", {"fecha": f, "aplicacion": recurso}, "plantilla", "tu")


def gen_consultar_contexto(n):
    frases = [
        ("¿qué estaba haciendo?", "reciente"), ("¿en qué me quedé?", "reciente"),
        ("¿qué tenía abierto hace rato?", "reciente"), ("recuérdame qué estaba haciendo", "reciente"),
        ("¿en qué estaba trabajando esta mañana?", "hoy"), ("¿qué estaba haciendo antes del almuerzo?", "hoy"),
        ("¿qué fue lo último que hice?", "reciente"), ("decime en qué me quedé", "reciente"),
        ("¿qué archivo estaba editando?", "reciente"), ("¿en qué andaba hace una hora?", "ultima_hora"),
    ]
    for _ in range(n):
        f, rango = random.choice(frases)
        agregar(cortesia(f), "consultar_contexto", {"rango_tiempo": rango}, "plantilla",
                "vos" if f.startswith("decime") else "tu")


def gen_continuar_actividad(n):
    frases = ["continúa donde lo dejé", "sigamos con lo de antes", "retoma lo que estaba haciendo",
              "abre lo que tenía la última vez", "volvamos a lo que estaba haciendo",
              "seguí donde me quedé", "restaura mi sesión anterior", "quiero continuar con mi trabajo de ayer"]
    for _ in range(n):
        f = random.choice(frases)
        agregar(cortesia(f), "continuar_actividad", {}, "plantilla",
                "vos" if f.startswith("seguí") else "tu")


def gen_responder_sugerencia(n):
    frases = [("sí, dale", "aceptar"), ("sí, por favor", "aceptar"), ("dale pues", "aceptar"),
              ("va, hacelo", "aceptar"), ("claro, ábrelo", "aceptar"), ("no, gracias", "rechazar"),
              ("no, déjalo así", "rechazar"), ("no quiero", "rechazar"), ("ahorita no", "posponer"),
              ("mejor después", "posponer"), ("recuérdamelo más tarde", "posponer")]
    contexto = random.choice
    sugerencias = ["Sueles abrir Spotify a esta hora. ¿Quieres que lo abra?",
                   "¿Inicio tu rutina de estudio como todos los lunes?",
                   "La última vez dejaste abierto el informe de IA. ¿Lo abro?"]
    for _ in range(n):
        f, r = random.choice(frases)
        agregar(f, "responder_sugerencia", {"respuesta": r}, "plantilla",
                "vos" if "hacelo" in f else "tu", contexto="Sugerencia del asistente: " + contexto(sugerencias))


def gen_conversacion_general(n):
    frases = ["explícame qué es la inteligencia artificial", "¿qué es un modelo de lenguaje?",
              "dame un consejo para estudiar mejor", "cuéntame un chiste", "¿cómo se dice computadora en inglés?",
              "¿qué diferencia hay entre RAM y disco duro?", "resúmeme qué es el aprendizaje automático",
              "¿cuál es la capital de Costa Rica?", "dame ideas para organizar mi semana",
              "¿qué significa la sigla CPU?", "hola, ¿cómo estás?", "gracias por la ayuda",
              "¿qué puedes hacer?", "explicame qué es una red neuronal", "¿cuánto es 15 por 12?"]
    for _ in range(n):
        f = random.choice(frases)
        agregar(cortesia(f) if random.random() < 0.3 else f, "conversacion_general", {}, "plantilla",
                "vos" if f.startswith("explicame") else "tu")


def gen_ambigua(n):
    frases = ["ábrelo", "búscalo", "abre eso", "ponelo", "haz lo otro", "abre el archivo",
              "busca la cosa esa", "ejecútalo", "ábreme eso que te dije", "abre la carpeta",
              "pon lo de siempre", "eso"]
    for _ in range(n):
        f = random.choice(frases)
        agregar(f, "ambigua", {}, "plantilla", "vos" if f == "ponelo" else "tu")


def gen_fuera_de_alcance(n):
    frases = ["envíale un correo a mi profesor", "compra boletos para el cine", "borra todos mis archivos",
              "formatea el disco", "pide una pizza", "llama a mi mamá", "descarga una película pirata",
              "hackea el wifi del vecino", "transfiere dinero a mi cuenta", "desinstala el antivirus",
              "publica esto en Facebook", "elimina la carpeta de Windows"]
    for _ in range(n):
        agregar(cortesia(random.choice(frases)), "fuera_de_alcance", {}, "plantilla", "tu")


# ------------------------------------------------------------------
# 2) Ejemplos redactados uno a uno (más naturales / coloquiales)
# ------------------------------------------------------------------
REDACTADOS = [
    ("necesito el navegador para revisar el aula virtual", "abrir_aplicacion", {"aplicacion": "navegador"}, "perifrasis"),
    ("abrime Word que voy a hacer la tarea", "abrir_aplicacion", {"aplicacion": "word"}, "vos"),
    ("ponme algo de música en Spotify", "abrir_aplicacion", {"aplicacion": "spotify"}, "tu"),
    ("voy a programar, abre VS Code", "abrir_aplicacion", {"aplicacion": "vscode"}, "tu"),
    ("tengo clase por Zoom, ábrelo", "abrir_aplicacion", {"aplicacion": "zoom"}, "tu"),
    ("quiero hacer unas cuentas, abre la calculadora", "abrir_aplicacion", {"aplicacion": "calculadora"}, "tu"),
    ("abrí el Excel para el presupuesto", "abrir_aplicacion", {"aplicacion": "excel"}, "vos"),
    ("me abres Teams que ya empieza la reunión", "abrir_aplicacion", {"aplicacion": "teams"}, "perifrasis"),
    ("llévame a mis descargas", "abrir_carpeta", {"carpeta": "descargas"}, "tu"),
    ("enséñame lo que tengo en el escritorio", "abrir_carpeta", {"carpeta": "escritorio"}, "tu"),
    ("quiero ver mis fotos", "abrir_carpeta", {"carpeta": "imagenes"}, "perifrasis"),
    ("entrá a mis videos", "abrir_carpeta", {"carpeta": "videos"}, "vos"),
    ("abre la carpeta donde guardo mis documentos", "abrir_carpeta", {"carpeta": "documentos"}, "tu"),
    ("abre el informe de IA que estaba haciendo", "abrir_archivo", {"nombre": "informe de inteligencia artificial", "extension": "docx"}, "tu"),
    ("necesito ver mi horario de clases", "abrir_archivo", {"nombre": "horario de clases", "extension": "pdf"}, "perifrasis"),
    ("abrime las notas de la reunión", "abrir_archivo", {"nombre": "notas de la reunión", "extension": "txt"}, "vos"),
    ("muéstrame el presupuesto del mes", "abrir_archivo", {"nombre": "presupuesto del mes", "extension": "xlsx"}, "tu"),
    ("¿dónde guardé el PDF de redes?", "buscar_archivo", {"consulta": "redes", "extension": "pdf"}, "tu"),
    ("no encuentro la foto del carnet, búscala", "buscar_archivo", {"consulta": "foto del carnet", "extension": "jpg"}, "tu"),
    ("buscame el contrato que me mandaron", "buscar_archivo", {"consulta": "contrato", "extension": None}, "vos"),
    ("tengo que encontrar las diapositivas de IA", "buscar_archivo", {"consulta": "diapositivas de IA", "extension": "pptx"}, "perifrasis"),
    ("me equivoqué, no apagues nada", "ejecutar_comando", {"comando": "cancelar_apagado", "requiere_confirmacion": False}, "tu"),
    ("estoy en clase, silencia la compu", "ejecutar_comando", {"comando": "silenciar_volumen", "requiere_confirmacion": False}, "tu"),
    ("me voy a almorzar, bloqueá la pantalla", "ejecutar_comando", {"comando": "bloquear_pantalla", "requiere_confirmacion": False}, "vos"),
    ("ya terminé por hoy, apaga la compu", "ejecutar_comando", {"comando": "apagar_equipo", "requiere_confirmacion": True}, "tu"),
    ("no se escucha nada, súbele", "ejecutar_comando", {"comando": "subir_volumen", "requiere_confirmacion": False}, "tu"),
    ("cada vez que diga modo estudio abre Word y el navegador", "crear_rutina", {"nombre": "estudio", "acciones": [{"intencion": "abrir_aplicacion", "parametros": {"aplicacion": "word"}}, {"intencion": "abrir_aplicacion", "parametros": {"aplicacion": "navegador"}}]}, "tu"),
    ("guardame una rutina para programar con VS Code y la terminal", "crear_rutina", {"nombre": "programación", "acciones": [{"intencion": "abrir_aplicacion", "parametros": {"aplicacion": "vscode"}}, {"intencion": "abrir_aplicacion", "parametros": {"aplicacion": "terminal"}}]}, "vos"),
    ("voy a estudiar, prepárame todo", "ejecutar_rutina", {"nombre": "estudio"}, "tu"),
    ("arrancá lo del trabajo", "ejecutar_rutina", {"nombre": "trabajo"}, "vos"),
    ("ya llegué, pon la rutina de la mañana", "ejecutar_rutina", {"nombre": "mañana"}, "tu"),
    ("se me fue la luz, ¿qué estaba haciendo?", "consultar_contexto", {"rango_tiempo": "reciente"}, "tu"),
    ("me distraje, ¿en qué iba?", "consultar_contexto", {"rango_tiempo": "reciente"}, "tu"),
    ("se reinició la compu, deja todo como estaba", "continuar_actividad", {}, "tu"),
    ("abrí otra vez lo que tenía antes de apagar", "continuar_actividad", {}, "vos"),
    ("ya terminé de escuchar música, cierra Spotify", "cerrar_aplicacion", {"aplicacion": "spotify"}, "tu"),
    ("apaga el Word que ya terminé", "cerrar_aplicacion", {"aplicacion": "word"}, "tu"),
    ("cerrá el YouTube que me distrae", "cerrar_aplicacion", {"aplicacion": "youtube"}, "vos"),
    ("ponme algo en YouTube", "abrir_aplicacion", {"aplicacion": "youtube"}, "tu"),
    ("¿cuánto tiempo usé el navegador hoy?", "consultar_historial", {"fecha": "hoy", "aplicacion": "navegador"}, "tu"),
    ("¿qué documentos revisé el lunes?", "consultar_historial", {"fecha": "lunes", "aplicacion": None}, "tu"),
    ("simón, ábrelo", "responder_sugerencia", {"respuesta": "aceptar"}, "tu"),
    ("no, ahorita estoy ocupado", "responder_sugerencia", {"respuesta": "posponer"}, "tu"),
    ("¿por qué el cielo es azul?", "conversacion_general", {}, "tu"),
    ("ayudame a redactar un mensaje para mi profe", "conversacion_general", {}, "vos"),
    ("¿qué es Python?", "conversacion_general", {}, "tu"),
    ("abrilo", "ambigua", {}, "vos"),
    ("haz lo mismo que ayer", "ambigua", {}, "tu"),
    ("borra la carpeta System32", "fuera_de_alcance", {}, "tu"),
    ("mándale un WhatsApp a Kenneth", "fuera_de_alcance", {}, "tu"),
    ("instálame Photoshop gratis", "fuera_de_alcance", {}, "tu"),
]


def main():
    # Volumen objetivo por intención (deliberadamente no uniforme: refleja uso esperado)
    gen_abrir_aplicacion(120)
    gen_cerrar_aplicacion(70)
    gen_abrir_carpeta(80)
    gen_abrir_archivo(90)
    gen_buscar_archivo(80)
    gen_ejecutar_comando(85)
    gen_crear_rutina(55)
    gen_ejecutar_rutina(60)
    gen_consultar_historial(60)
    gen_consultar_contexto(55)
    gen_continuar_actividad(45)
    gen_responder_sugerencia(50)
    gen_conversacion_general(70)
    gen_ambigua(40)
    gen_fuera_de_alcance(45)

    for instr, intencion, params, reg in REDACTADOS:
        agregar(instr, intencion, params, "redactado", reg)

    random.shuffle(registros)
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as f:
        for i, r in enumerate(registros, start=1):
            r = {"id": f"v0-{i:05d}", **r}
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Registros generados: {len(registros)} -> {SALIDA}")


# ------------------------------------------------------------------
# 3) Ejemplos complementarios v1 (añadidos tras el EDA de v0)
#    El EDA mostró baja diversidad en intenciones de frase cerrada
#    (ambigua, responder_sugerencia, conversacion_general). Se guardan en
#    un archivo crudo aparte para no modificar dataset_v0.jsonl.
# ------------------------------------------------------------------
SALIDA_V1 = os.path.join(RAIZ, "data", "raw", "complemento_v1.jsonl")

SUGERENCIAS = ["Sueles abrir Spotify a esta hora. ¿Quieres que lo abra?",
               "¿Inicio tu rutina de estudio como todos los lunes?",
               "La última vez dejaste abierto el informe de IA. ¿Lo abro?"]

COMPLEMENTO_V1 = [
    *[(t, "ambigua", {}, r) for t, r in [
        ("abre ese", "tu"), ("búscame eso", "tu"), ("ponlo", "tu"), ("hacé lo que te pedí", "vos"),
        ("el de ayer", "tu"), ("abre la otra", "tu"), ("busca aquello", "tu"), ("abre el programa", "tu"),
        ("abre el documento", "tu"), ("quiero ese archivo", "perifrasis"), ("lo de siempre", "tu"),
        ("mostrame aquello", "vos"), ("abre lo que te dije", "tu"), ("busca el que tiene el nombre largo", "tu"),
        ("esa carpeta", "tu"), ("ejecuta el que te mencioné", "tu"), ("pon eso otra vez", "tu"),
        ("abre una", "tu"), ("necesito el archivo ese", "perifrasis"), ("ábreme el de la U", "tu")]],
    *[(t, "responder_sugerencia", {"respuesta": a}, r) for t, a, r in [
        ("sí", "aceptar", "tu"), ("dale, ábrelo", "aceptar", "tu"), ("ok", "aceptar", "tu"),
        ("de acuerdo", "aceptar", "tu"), ("perfecto, hazlo", "aceptar", "tu"), ("sí, iníciala", "aceptar", "tu"),
        ("claro que sí", "aceptar", "tu"), ("sale", "aceptar", "tu"), ("afirmativo", "aceptar", "tu"),
        ("no", "rechazar", "tu"), ("no hace falta", "rechazar", "tu"), ("nel", "rechazar", "tu"),
        ("para nada", "rechazar", "tu"), ("no, eso no", "rechazar", "tu"), ("en un rato", "posponer", "tu"),
        ("más tarde", "posponer", "tu"), ("después lo vemos", "posponer", "tu"),
        ("dentro de diez minutos", "posponer", "tu"), ("todavía no", "posponer", "tu"),
        ("avisame después", "posponer", "vos")]],
    *[(t, "conversacion_general", {}, r) for t, r in [
        ("dame una receta fácil para la cena", "tu"), ("¿quién inventó la computadora?", "tu"),
        ("explícame qué es la nube", "tu"), ("¿cómo hago una tabla en Word?", "tu"),
        ("recomiéndame un libro", "tu"), ("¿qué es un algoritmo?", "tu"),
        ("traduce buenos días al inglés", "tu"), ("¿qué es la memoria caché?", "tu"),
        ("dame tips para una exposición", "tu"), ("buenas noches", "tu"),
        ("¿qué opinás de Python?", "vos"), ("¿para qué sirve un sistema operativo?", "tu")]],
]


def generar_complemento():
    random.seed(SEMILLA + 1)
    filas = []
    for i, (instr, intencion, params, reg) in enumerate(COMPLEMENTO_V1, start=1):
        categoria, rf = CATALOGO[intencion]
        filas.append({
            "id": f"v1-{i:05d}", "instruccion": instr,
            "contexto": ("Sugerencia del asistente: " + random.choice(SUGERENCIAS)) if intencion == "responder_sugerencia" else None,
            "intencion": intencion, "parametros": params, "categoria": categoria,
            "requerimiento": rf, "registro": reg, "origen": "redactado",
        })
    with open(SALIDA_V1, "w", encoding="utf-8") as f:
        for r in filas:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Complemento v1: {len(filas)} -> {SALIDA_V1}")


if __name__ == "__main__":
    main()
    generar_complemento()
