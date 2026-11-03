from patrones import GestorPatrones
from observador_pc import ObservadorPC
from sugerencias import GestorSugerencias
from respuesta_sugerencia import GestorRespuestaSugerencia
from cerebro_patrones import CerebroPatrones


class CerebroIntegrador:

    def __init__(self):

        print("\n========================================")
        print("   CEREBRO INTEGRADOR - ASISTENTE IA")
        print("========================================\n")

        # =========================================
        # COMPONENTES
        # =========================================

        self.patrones = GestorPatrones()

        self.observador = ObservadorPC(
            self.patrones
        )

        self.sugerencias = GestorSugerencias()

        self.respuestas = GestorRespuestaSugerencia()

        self.cerebro = CerebroPatrones()

        # =========================================
        # COMPROBAR CEREBRO
        # =========================================

        print("[Integrador] Comprobando conexión con Qwen...")

        if self.cerebro.comprobar_conexion():

            print("[Integrador] ✓ Cerebro disponible.")

        else:

            print("[Integrador] ✗ Cerebro no disponible.")

        print()


    # =================================================
    # SIMULAR FALLO DE APERTURA
    # =================================================

    def simular_fallo_apertura(
        self,
        aplicacion,
        proceso
    ):

        print("\n----------------------------------------")
        print("SIMULANDO FALLO")
        print("----------------------------------------")

        resultado = self.observador.comprobar_apertura(
            aplicacion,
            proceso
        )

        print("\nResultado recibido:")
        print(resultado)

        return resultado


    # =================================================
    # PROCESAR RESULTADO
    # =================================================

    def procesar_resultado(self, resultado):

        if not resultado:

            print(
                "[Integrador] No se recibió ningún resultado."
            )

            return


        # =============================================
        # SI LA APLICACIÓN FUNCIONÓ
        # =============================================

        if resultado.get("exito", False):

            print(
                "[Integrador] La aplicación funcionó correctamente."
            )

            return


        # =============================================
        # OBTENER INFORMACIÓN DEL PATRÓN
        # =============================================

        patron = resultado.get(
            "patron",
            {}
        )

        if not patron:

            print(
                "[Integrador] No se recibió información del patrón."
            )

            return


        # =============================================
        # COMPROBAR SI SE DETECTÓ EL PATRÓN
        # =============================================

        if not patron.get("detectado", False):

            print(
                "[Integrador] Fallo registrado, "
                "pero todavía no se ha alcanzado el patrón."
            )

            return


        # =============================================
        # PATRÓN DETECTADO
        # =============================================

        print("\n========================================")
        print("       ¡PATRÓN DETECTADO!")
        print("========================================")

        nombre = patron.get(
            "nombre",
            resultado.get(
                "aplicacion",
                "Aplicación desconocida"
            )
        )

        fallos = patron.get(
            "fallos",
            0
        )

        proceso = resultado.get(
            "proceso",
            "Proceso desconocido"
        )

        print(f"Aplicación : {nombre}")
        print(f"Fallos     : {fallos}")
        print(f"Proceso    : {proceso}")
        print()


        # =============================================
        # CONTEXTO COMPLETO DEL PROBLEMA
        # =============================================

        patron_completo = {

            "detectado": True,

            "nombre": nombre,

            "fallos": fallos,

            "proceso": proceso,

            "tipo": "fallo_apertura",

            "origen": "ObservadorPC"
        }


        # =============================================
        # MENSAJE DE SUGERENCIA
        # =============================================

        mensaje = (
            f"He detectado que has tenido problemas "
            f"para abrir {nombre}. "
            f"Ya ocurrió {fallos} veces. "
            f"¿Quieres que te ayude?"
        )


        # =============================================
        # CALLBACK
        # =============================================

        def respuesta_usuario(respuesta):

            self.procesar_respuesta_usuario(
                respuesta,
                patron_completo
            )


        # =============================================
        # MOSTRAR SUGERENCIA
        # =============================================

        print(
            "[Integrador] Mostrando sugerencia..."
        )

        self.sugerencias.mostrar_sugerencia(

            mensaje=mensaje,

            tipo="problema",

            titulo="Asistente IA",

            callback_externo=respuesta_usuario
        )


    # =================================================
    # PROCESAR RESPUESTA DEL USUARIO
    # =================================================

    def procesar_respuesta_usuario(
        self,
        respuesta,
        patron
    ):

        print("\n----------------------------------------")
        print("RESPUESTA DEL USUARIO")
        print("----------------------------------------")

        print(
            "Respuesta:",
            respuesta
        )


        # =============================================
        # PROCESAR RESPUESTA
        # =============================================

        resultado = self.respuestas.procesar_respuesta(
            respuesta,
            patron
        )

        print("\nResultado de respuesta:")
        print(resultado)


        # =============================================
        # USUARIO QUIERE AYUDA
        # =============================================

        if respuesta == "ayudar":

            print(
                "\n[Integrador] El usuario quiere ayuda."
            )

            contexto = resultado.get(
                "contexto"
            )

            if not contexto:

                print(
                    "[Integrador] No existe contexto "
                    "para consultar al cerebro."
                )

                return


            # =========================================
            # CONSULTAR QWEN
            # =========================================

            print(
                "[Integrador] Enviando problema al cerebro..."
            )

            respuesta_cerebro = self.cerebro.consultar(
                contexto
            )


            # =========================================
            # MOSTRAR RESPUESTA
            # =========================================

            print("\n========================================")
            print("        RESPUESTA DEL CEREBRO")
            print("========================================\n")

            print(
                respuesta_cerebro
            )

            print("\n========================================")


        # =============================================
        # USUARIO ELIGE AHORA NO
        # =============================================

        elif respuesta == "ahora_no":

            print(
                "[Integrador] El usuario decidió "
                "no recibir ayuda ahora."
            )


        else:

            print(
                "[Integrador] Respuesta no reconocida."
            )


    # =================================================
    # PRUEBA DE CADENA COMPLETA
    # =================================================

    def prueba_cadena_completa(self):

        aplicacion = "AplicacionDePrueba"

        proceso = (
            "proceso_falso_integracion_12345.exe"
        )


        # =============================================
        # REINICIAR SOLO EL EPISODIO
        # =============================================

        print("\n========================================")
        print("REINICIANDO EPISODIO DE PRUEBA")
        print("========================================")

        self.patrones.reiniciar_aplicacion(
            aplicacion,
            borrar_historico=False
        )

        print(
            "[Integrador] Episodio reiniciado correctamente."
        )

        print(
            "[Integrador] El historial anterior "
            "se conserva."
        )


        # =============================================
        # SIMULAR 3 FALLOS
        # =============================================

        for numero in range(1, 4):

            print("\n")
            print("========================================")
            print(f"          FALLO {numero} DE 3")
            print("========================================")


            resultado = self.simular_fallo_apertura(
                aplicacion,
                proceso
            )


            self.procesar_resultado(
                resultado
            )


        # =============================================
        # FIN DE LA PRUEBA
        # =============================================

        print("\n========================================")
        print("       PRUEBA FINALIZADA")
        print("========================================")

        print()


# =====================================================
# EJECUCIÓN DIRECTA
# =====================================================

if __name__ == "__main__":

    integrador = CerebroIntegrador()

    integrador.prueba_cadena_completa()
    