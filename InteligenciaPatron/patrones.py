import os
import json
import time
import threading


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

MEMORIA_ARCHIVO = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "memoria_patrones.json"
)


# ============================================================
# AJUSTES DEL SISTEMA
# ============================================================

# Número de fallos consecutivos necesarios para detectar
# un patrón.
MAX_INTENTOS_FALLIDOS = 3


# Si pasa este tiempo sin nuevos fallos, consideramos
# que comenzó un episodio nuevo.
TIEMPO_NUEVO_EPISODIO = 15 * 60  # 15 minutos


# Cantidad máxima de eventos guardados.
MAX_EVENTOS = 200


# Cantidad máxima de patrones detectados guardados.
MAX_PATRONES = 50


# ============================================================
# ESTRUCTURA DE MEMORIA
# ============================================================

def crear_memoria_vacia():
    """
    Crea una estructura de memoria nueva.
    """

    return {
        "aplicaciones": {},
        "eventos": [],
        "patrones_detectados": []
    }


# ============================================================
# GESTOR DE PATRONES
# ============================================================

class GestorPatrones:

    def __init__(self):

        self._lock = threading.Lock()

        self.memoria = crear_memoria_vacia()

        self._cargar_memoria()


    # ========================================================
    # MEMORIA
    # ========================================================

    def _cargar_memoria(self):

        try:

            if not os.path.isfile(MEMORIA_ARCHIVO):

                self._guardar_memoria()

                return


            with open(
                MEMORIA_ARCHIVO,
                "r",
                encoding="utf-8"
            ) as archivo:

                datos = json.load(archivo)


            if not isinstance(datos, dict):

                return


            # ------------------------------------------------
            # Nos aseguramos de que existan las tres
            # secciones principales.
            # ------------------------------------------------

            memoria_base = crear_memoria_vacia()

            memoria_base.update(datos)

            if not isinstance(
                memoria_base.get("aplicaciones"),
                dict
            ):
                memoria_base["aplicaciones"] = {}


            if not isinstance(
                memoria_base.get("eventos"),
                list
            ):
                memoria_base["eventos"] = []


            if not isinstance(
                memoria_base.get("patrones_detectados"),
                list
            ):
                memoria_base["patrones_detectados"] = []


            self.memoria = memoria_base


        except Exception:

            # Si el archivo está dañado, comenzamos
            # con una memoria limpia.

            self.memoria = crear_memoria_vacia()


    # ========================================================
    # GUARDAR MEMORIA
    # ========================================================

    def _guardar_memoria(self):

        try:

            carpeta = os.path.dirname(
                MEMORIA_ARCHIVO
            )

            os.makedirs(
                carpeta,
                exist_ok=True
            )


            archivo_temporal = (
                MEMORIA_ARCHIVO + ".tmp"
            )


            with open(
                archivo_temporal,
                "w",
                encoding="utf-8"
            ) as archivo:

                json.dump(
                    self.memoria,
                    archivo,
                    ensure_ascii=False,
                    indent=4
                )


            # Reemplazo seguro
            os.replace(
                archivo_temporal,
                MEMORIA_ARCHIVO
            )


        except Exception:

            pass


    # ========================================================
    # REGISTRAR EVENTO
    # ========================================================

    def registrar_evento(
        self,
        tipo,
        nombre,
        detalles=None
    ):

        ahora = time.time()


        evento = {

            "tipo": tipo,

            "nombre": nombre,

            "detalles": detalles or {},

            "timestamp": ahora
        }


        with self._lock:

            self.memoria["eventos"].append(
                evento
            )


            # Conservamos solamente los últimos
            # eventos.
            self.memoria["eventos"] = (
                self.memoria["eventos"][
                    -MAX_EVENTOS:
                ]
            )


            self._guardar_memoria()


        return evento


    # ========================================================
    # REGISTRAR FALLO
    # ========================================================

    def registrar_fallo(
        self,
        nombre,
        detalles=None
    ):

        ahora = time.time()


        with self._lock:

            aplicaciones = (
                self.memoria["aplicaciones"]
            )


            # ------------------------------------------------
            # Crear registro si no existe
            # ------------------------------------------------

            if nombre not in aplicaciones:

                aplicaciones[nombre] = {

                    "fallos": 0,

                    "total_fallos": 0,

                    "ultimo_fallo": 0,

                    "alerta_mostrada": False,

                    "veces_ayudado": 0
                }


            datos = aplicaciones[nombre]


            ultimo_fallo = datos.get(
                "ultimo_fallo",
                0
            )


            # ------------------------------------------------
            # NUEVO EPISODIO
            # ------------------------------------------------

            if (
                ultimo_fallo > 0
                and
                ahora - ultimo_fallo
                > TIEMPO_NUEVO_EPISODIO
            ):

                datos["fallos"] = 0

                datos["alerta_mostrada"] = False


            # ------------------------------------------------
            # INCREMENTAR CONTADORES
            # ------------------------------------------------

            datos["fallos"] += 1

            datos["total_fallos"] += 1

            datos["ultimo_fallo"] = ahora


            # ------------------------------------------------
            # GUARDAR EVENTO
            # ------------------------------------------------

            self.memoria["eventos"].append({

                "tipo": "fallo",

                "nombre": nombre,

                "detalles": detalles or {},

                "timestamp": ahora

            })


            self.memoria["eventos"] = (
                self.memoria["eventos"][
                    -MAX_EVENTOS:
                ]
            )


            # ------------------------------------------------
            # COMPROBAR PATRÓN
            # ------------------------------------------------

            necesita_ayuda = (

                datos["fallos"]
                >= MAX_INTENTOS_FALLIDOS

                and

                not datos["alerta_mostrada"]
            )


            # ------------------------------------------------
            # PATRÓN DETECTADO
            # ------------------------------------------------

            if necesita_ayuda:

                datos["alerta_mostrada"] = True


                self.memoria[
                    "patrones_detectados"
                ].append({

                    "tipo":
                        "fallos_repetidos",

                    "nombre":
                        nombre,

                    "fallos":
                        datos["fallos"],

                    "timestamp":
                        ahora

                })


                self.memoria[
                    "patrones_detectados"
                ] = (

                    self.memoria[
                        "patrones_detectados"
                    ][-MAX_PATRONES:]

                )


            self._guardar_memoria()


            # ------------------------------------------------
            # RESULTADO
            # ------------------------------------------------

            return {

                "detectado":
                    necesita_ayuda,

                "nombre":
                    nombre,

                "fallos":
                    datos["fallos"],

                "total_fallos":
                    datos["total_fallos"],

                "mensaje":
                    (
                        f"Se detectaron "
                        f"{datos['fallos']} "
                        f"fallos con "
                        f"{nombre}."
                    )
            }


    # ========================================================
    # MARCAR PROBLEMA COMO ATENDIDO
    # ========================================================

    def marcar_ayudado(
        self,
        nombre
    ):

        with self._lock:

            if (
                nombre
                not in self.memoria["aplicaciones"]
            ):

                return False


            datos = (
                self.memoria[
                    "aplicaciones"
                ][nombre]
            )


            datos["veces_ayudado"] = (

                datos.get(
                    "veces_ayudado",
                    0
                )

                + 1
            )


            # Reiniciamos solamente el episodio
            # actual.
            datos["fallos"] = 0


            # Permitimos detectar otro episodio
            # en el futuro.
            datos["alerta_mostrada"] = False


            self._guardar_memoria()


            return True


    # ========================================================
    # REINICIAR UNA APLICACIÓN
    # ========================================================

    def reiniciar_aplicacion(
        self,
        nombre,
        borrar_historico=False
    ):
        """
        Reinicia los datos de una aplicación.

        borrar_historico=False:
            Conserva total_fallos.

        borrar_historico=True:
            Elimina completamente el registro.
        """

        with self._lock:

            if (
                nombre
                not in self.memoria["aplicaciones"]
            ):

                return False


            if borrar_historico:

                del self.memoria[
                    "aplicaciones"
                ][nombre]

            else:

                datos = self.memoria[
                    "aplicaciones"
                ][nombre]

                datos["fallos"] = 0

                datos["ultimo_fallo"] = 0

                datos["alerta_mostrada"] = False


            self._guardar_memoria()


            return True


    # ========================================================
    # LIMPIAR TODA LA MEMORIA
    # ========================================================

    def limpiar_memoria(
        self,
        confirmar=False
    ):
        """
        Borra toda la memoria de patrones.

        Es necesario confirmar explícitamente.
        """

        if not confirmar:

            return False


        with self._lock:

            self.memoria = (
                crear_memoria_vacia()
            )

            self._guardar_memoria()


        return True


    # ========================================================
    # OBTENER INFORMACIÓN
    # ========================================================

    def obtener_aplicacion(
        self,
        nombre
    ):

        with self._lock:

            datos = self.memoria[
                "aplicaciones"
            ].get(nombre)


            if datos is None:

                return None


            return dict(datos)


    # ========================================================
    # OBTENER PATRONES
    # ========================================================

    def obtener_patrones(self):

        with self._lock:

            return list(
                self.memoria[
                    "patrones_detectados"
                ]
            )


    # ========================================================
    # OBTENER EVENTOS
    # ========================================================

    def obtener_eventos(
        self,
        limite=20
    ):

        with self._lock:

            return list(
                self.memoria[
                    "eventos"
                ][-limite:]
            )


    # ========================================================
    # LIMPIAR EVENTOS ANTIGUOS
    # ========================================================

    def limpiar_eventos_antiguos(
        self,
        dias=30
    ):

        limite = (

            time.time()

            - dias
            * 24
            * 60
            * 60
        )


        with self._lock:

            self.memoria["eventos"] = [

                evento

                for evento
                in self.memoria["eventos"]

                if evento.get(
                    "timestamp",
                    0
                ) >= limite
            ]


            self._guardar_memoria()

# ============================================================
# PRUEBA DIRECTA
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 55)
    print(" PRUEBA DEL DETECTOR DE PATRONES")
    print("=" * 55)
    print()


    gestor = GestorPatrones()


    # --------------------------------------------------------
    # Limpiamos SOLO la aplicación de prueba.
    #
    # No tocamos las demás aplicaciones que pudiera haber
    # aprendido el asistente en el futuro.
    # --------------------------------------------------------

    gestor.reiniciar_aplicacion(
        "AplicacionDePrueba",
        borrar_historico=True
    )


    print(
        "Iniciando prueba limpia..."
    )

    print()


    # --------------------------------------------------------
    # Tres fallos
    # --------------------------------------------------------

    for intento in range(
        1,
        MAX_INTENTOS_FALLIDOS + 1
    ):

        resultado = gestor.registrar_fallo(

            "AplicacionDePrueba",

            {
                "motivo":
                    "Prueba del sistema"
            }
        )


        print(

            f"Intento {intento}: "
            f"{resultado['mensaje']}"

        )


        if resultado["detectado"]:

            print()
            print(
                ">>> PATRÓN DETECTADO"
            )
            print()


    # --------------------------------------------------------
    # Mostrar información final
    # --------------------------------------------------------

    datos = gestor.obtener_aplicacion(
        "AplicacionDePrueba"
    )


    print(
        "Información de la prueba:"
    )

    print(
        f"Fallos actuales: "
        f"{datos['fallos']}"
    )

    print(
        f"Fallos históricos: "
        f"{datos['total_fallos']}"
    )

    print(
        f"Alerta mostrada: "
        f"{datos['alerta_mostrada']}"
    )


    print()
    print(
        "Memoria guardada en:"
    )

    print(
        MEMORIA_ARCHIVO
    )

    print()