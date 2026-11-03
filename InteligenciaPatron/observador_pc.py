import time
import threading

import psutil


# ============================================================
# CONFIGURACIÓN
# ============================================================

# Tiempo máximo para comprobar si una aplicación apareció.
TIEMPO_COMPROBACION = 5


# ============================================================
# OBSERVADOR DEL PC
# ============================================================

class ObservadorPC:

    def __init__(self, gestor_patrones):

        self.gestor_patrones = gestor_patrones

        self.activo = False

        self._hilo = None

        self._lock = threading.Lock()


    # ========================================================
    # INICIAR OBSERVADOR
    # ========================================================

    def iniciar(self):

        with self._lock:

            if self.activo:
                return False

            self.activo = True


            self._hilo = threading.Thread(
                target=self._bucle,
                daemon=True
            )


            self._hilo.start()


        print(
            "[ObservadorPC] Observador iniciado."
        )


        return True


    # ========================================================
    # DETENER OBSERVADOR
    # ========================================================

    def detener(self):

        with self._lock:

            self.activo = False


        print(
            "[ObservadorPC] Observador detenido."
        )


    # ========================================================
    # BUCLE PRINCIPAL
    # ========================================================

    def _bucle(self):

        while self.activo:

            try:

                # ------------------------------------------------
                # En esta primera versión no hacemos análisis
                # permanente del PC.
                #
                # Esto evita consumir CPU innecesariamente.
                #
                # Más adelante aquí podremos agregar observadores
                # concretos.
                # ------------------------------------------------

                time.sleep(2)


            except Exception as error:

                print(
                    "[ObservadorPC] Error:",
                    error
                )

                time.sleep(2)


    # ========================================================
    # COMPROBAR SI UN PROCESO EXISTE
    # ========================================================

    def proceso_existe(
        self,
        nombre_proceso
    ):

        nombre_proceso = (
            nombre_proceso.lower()
        )


        try:

            for proceso in psutil.process_iter(
                ["name"]
            ):

                try:

                    nombre = proceso.info[
                        "name"
                    ]


                    if not nombre:
                        continue


                    if (
                        nombre.lower()
                        ==
                        nombre_proceso
                    ):

                        return True


                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied
                ):

                    continue


        except Exception as error:

            print(
                "[ObservadorPC] Error comprobando proceso:",
                error
            )


        return False


    # ========================================================
    # ESPERAR A QUE APAREZCA UN PROCESO
    # ========================================================

    def esperar_proceso(
        self,
        nombre_proceso,
        tiempo_maximo=TIEMPO_COMPROBACION
    ):

        inicio = time.time()


        while (
            time.time() - inicio
            < tiempo_maximo
        ):

            if self.proceso_existe(
                nombre_proceso
            ):

                return True


            time.sleep(0.5)


        return False


    # ========================================================
    # REGISTRAR INTENTO DE APERTURA
    # ========================================================

    def comprobar_apertura(
        self,
        nombre_aplicacion,
        nombre_proceso
    ):

        """

        Comprueba si una aplicación realmente
        apareció después de intentar abrirla.

        IMPORTANTE:

        No consideramos que una aplicación
        falló simplemente porque se cerró.

        Solo registramos un fallo si:

        1. Se intentó abrir.
        2. El proceso no apareció.

        Esto reduce falsos positivos.
        """


        aparecio = self.esperar_proceso(
            nombre_proceso
        )


        if aparecio:

            print(
                f"[ObservadorPC] "
                f"{nombre_aplicacion} "
                f"se abrió correctamente."
            )


            return {

                "exito": True,

                "fallo": False,

                "aplicacion":
                    nombre_aplicacion,

                "proceso":
                    nombre_proceso
            }


        # ----------------------------------------------------
        # No apareció el proceso.
        # ----------------------------------------------------

        print(
            f"[ObservadorPC] "
            f"No se pudo confirmar la apertura de "
            f"{nombre_aplicacion}."
        )


        resultado = (
            self.gestor_patrones.registrar_fallo(

                nombre_aplicacion,

                {

                    "tipo":
                        "fallo_apertura",

                    "proceso":
                        nombre_proceso,

                    "observador":
                        "ObservadorPC"
                }
            )
        )


        return {

            "exito": False,

            "fallo": True,

            "aplicacion":
                nombre_aplicacion,

            "proceso":
                nombre_proceso,

            "patron":
                resultado
        }


    # ========================================================
    # REGISTRAR EVENTO NORMAL
    # ========================================================

    def registrar_evento(
        self,
        tipo,
        nombre,
        detalles=None
    ):

        return (
            self.gestor_patrones.registrar_evento(

                tipo,

                nombre,

                detalles
            )
        )

# ============================================================
# PRUEBA DIRECTA
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 55)
    print(" PRUEBA DE COMUNICACIÓN OBSERVADOR → PATRONES")
    print("=" * 55)
    print()


    # --------------------------------------------------------
    # Importar gestor de patrones
    # --------------------------------------------------------

    try:

        from patrones import GestorPatrones


    except ImportError:

        print(
            "ERROR: No se pudo importar patrones.py"
        )

        input(
            "\nPresiona ENTER para salir..."
        )

        raise SystemExit


    # --------------------------------------------------------
    # Crear gestor
    # --------------------------------------------------------

    gestor = GestorPatrones()


    # --------------------------------------------------------
    # Crear observador
    # --------------------------------------------------------

    observador = ObservadorPC(
        gestor
    )


    observador.iniciar()


    print()
    print(
        "Iniciando prueba controlada..."
    )

    print(
        "NO se modificará ningún programa de Windows."
    )

    print()


    # --------------------------------------------------------
    # Aplicación ficticia
    # --------------------------------------------------------

    nombre_aplicacion = (
        "AplicacionDePrueba"
    )


    nombre_proceso = (
        "proceso_falso_prueba_12345.exe"
    )


    # --------------------------------------------------------
    # Limpiar solamente esta aplicación
    # de las pruebas anteriores.
    # --------------------------------------------------------

    gestor.reiniciar_aplicacion(
        nombre_aplicacion,
        borrar_historico=True
    )


    # --------------------------------------------------------
    # Realizar 3 intentos
    # --------------------------------------------------------

    for intento in range(1, 4):

        print()
        print(
            "-" * 55
        )

        print(
            f"INTENTO {intento} DE 3"
        )

        print(
            "-" * 55
        )


        resultado = (
            observador.comprobar_apertura(

                nombre_aplicacion,

                nombre_proceso
            )
        )


        if resultado["fallo"]:

            patron = resultado["patron"]


            print()

            print(
                f"Fallos actuales: "
                f"{patron['fallos']}"
            )


            if patron["detectado"]:

                print()
                print(
                    ">>> PATRÓN DETECTADO <<<"
                )

            else:

                print(
                    "Todavía no se ha detectado "
                    "un patrón."
                )


    # --------------------------------------------------------
    # Mostrar información final
    # --------------------------------------------------------

    print()
    print("=" * 55)
    print(" RESULTADO FINAL")
    print("=" * 55)
    print()


    datos = gestor.obtener_aplicacion(
        nombre_aplicacion
    )


    if datos:

        print(
            f"Aplicación: "
            f"{nombre_aplicacion}"
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
        "Memoria utilizada:"
    )

    print(
        "memoria_patrones.json"
    )


    # --------------------------------------------------------
    # Detener observador
    # --------------------------------------------------------

    observador.detener()


    print()
    print(
        "Prueba finalizada correctamente."
    )

    print()


    input(
        "Presiona ENTER para cerrar..."
    )