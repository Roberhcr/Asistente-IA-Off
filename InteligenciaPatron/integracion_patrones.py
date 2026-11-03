from patrones import GestorPatrones
from observador_pc import ObservadorPC
from sugerencias import GestorSugerencias


class IntegradorPatrones:

    def __init__(self):

        print("[Integrador] Iniciando sistema...")

        # ==================================================
        # SISTEMA DE PATRONES
        # ==================================================

        self.patrones = GestorPatrones()

        # ==================================================
        # OBSERVADOR
        # ==================================================

        self.observador = ObservadorPC(
            gestor_patrones=self.patrones
        )

        # ==================================================
        # SUGERENCIAS
        # ==================================================

        self.sugerencias = GestorSugerencias()

        print(
            "[Integrador] Sistema iniciado correctamente."
        )


    # ======================================================
    # SIMULAR FALLA DE APERTURA
    # ======================================================

    def simular_fallo_apertura(
        self,
        aplicacion,
        proceso
    ):

        print()
        print("=" * 60)
        print(" SIMULANDO INTENTO DE APERTURA")
        print("=" * 60)
        print()

        print("Aplicación:", aplicacion)
        print("Proceso:", proceso)
        print()

        resultado = self.observador.comprobar_apertura(
            aplicacion,
            proceso
        )

        print()
        print("Resultado:")
        print(resultado)

        return resultado


    # ======================================================
    # PROCESAR RESULTADO
    # ======================================================

    def procesar_resultado(self, resultado):

        if not resultado:
            return

        # ==================================================
        # LA APLICACIÓN SE ABRIÓ
        # ==================================================

        if resultado.get("exito"):

            print()
            print(
                "[Integrador] La aplicación se abrió correctamente."
            )

            return

        # ==================================================
        # OBTENER INFORMACIÓN DEL PATRÓN
        # ==================================================

        patron = resultado.get("patron")

        if not patron:

            print()
            print(
                "[Integrador] Fallo registrado, "
                "pero no hay información del patrón."
            )

            return

        # ==================================================
        # IMPORTANTE:
        # SOLO ACTUAMOS SI REALMENTE SE DETECTÓ
        # UN PATRÓN.
        # ==================================================

        if not patron.get("detectado", False):

            print()
            print(
                "[Integrador] Fallo registrado."
            )

            print(
                "[Integrador] Todavía no se ha detectado "
                "un patrón."
            )

            print(
                "[Integrador] Fallos actuales:",
                patron.get("fallos", 0)
            )

            return

        # ==================================================
        # PATRÓN DETECTADO
        # ==================================================

        print()
        print("=" * 60)
        print(" PATRÓN DETECTADO")
        print("=" * 60)
        print()

        nombre = patron.get(
            "nombre",
            "Aplicación desconocida"
        )

        fallos = patron.get(
            "fallos",
            0
        )

        print(
            "Aplicación:",
            nombre
        )

        print(
            "Fallos consecutivos:",
            fallos
        )

        print()

        # ==================================================
        # ENVIAR SUGERENCIA
        # ==================================================

        self.mostrar_sugerencia_problema(
            patron
        )


    # ======================================================
    # MOSTRAR SUGERENCIA DE PROBLEMA
    # ======================================================

    def mostrar_sugerencia_problema(
        self,
        patron
    ):

        nombre = patron.get(
            "nombre",
            "una aplicación"
        )

        fallos = patron.get(
            "fallos",
            0
        )

        mensaje = (
            f"He detectado que {nombre} "
            f"ha fallado al abrirse {fallos} veces "
            "consecutivas.\n\n"
            "¿Quieres que te ayude a revisar "
            "el problema?"
        )

        print(
            "[Integrador] Enviando sugerencia de problema..."
        )

        self.sugerencias.mostrar_sugerencia(
            mensaje=mensaje,
            tipo="problema",
            titulo="Problema detectado"
        )


# ============================================================
# PRUEBA
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print(" PRUEBA DE INTEGRACIÓN DE PATRONES")
    print("=" * 60)
    print()

    sistema = IntegradorPatrones()

    aplicacion = "AplicacionDePrueba"

    proceso_falso = (
        "proceso_falso_integracion_12345.exe"
    )

    # ========================================================
    # LIMPIAR SOLAMENTE LOS FALLOS ACTUALES
    # DE LA APLICACIÓN DE PRUEBA
    # ========================================================

    sistema.patrones.reiniciar_aplicacion(
        aplicacion
    )

    print()
    print(
        "Comenzando prueba de 3 fallos..."
    )

    # ========================================================
    # FALLO 1
    # ========================================================

    resultado = sistema.simular_fallo_apertura(
        aplicacion,
        proceso_falso
    )

    sistema.procesar_resultado(
        resultado
    )


    # ========================================================
    # FALLO 2
    # ========================================================

    resultado = sistema.simular_fallo_apertura(
        aplicacion,
        proceso_falso
    )

    sistema.procesar_resultado(
        resultado
    )


    # ========================================================
    # FALLO 3
    # ========================================================

    resultado = sistema.simular_fallo_apertura(
        aplicacion,
        proceso_falso
    )

    sistema.procesar_resultado(
        resultado
    )


    print()
    print("=" * 60)
    print(" PRUEBA FINALIZADA")
    print("=" * 60)
    print()