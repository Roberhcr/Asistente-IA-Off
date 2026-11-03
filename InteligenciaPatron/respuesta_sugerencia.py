class GestorRespuestaSugerencia:
    """
    Gestiona la respuesta del usuario después de una sugerencia.

    Este módulo todavía NO se conecta con Qwen.
    Su función actual es preparar y comprobar el contexto
    que posteriormente recibirá el cerebro.
    """

    def __init__(self):
        self.ultima_respuesta = None
        self.ultimo_contexto = None

    def procesar_respuesta(self, respuesta, patron=None):
        """
        Procesa la respuesta del usuario.

        respuesta:
            "ayudar"      -> prepara el contexto para Qwen.
            "ahora_no"    -> registra que el usuario rechazó.
        """

        self.ultima_respuesta = respuesta

        if respuesta == "ayudar":
            return self._preparar_ayuda(patron)

        if respuesta == "ahora_no":
            return self._procesar_rechazo()

        print(
            "[RespuestaSugerencia] "
            "Respuesta no reconocida:",
            respuesta
        )

        return {
            "exito": False,
            "respuesta": respuesta,
            "accion": "ninguna",
            "contexto": None
        }

    def _preparar_ayuda(self, patron):
        """
        Prepara la información que posteriormente recibirá Qwen.
        """

        if not patron:
            print(
                "[RespuestaSugerencia] "
                "No se recibió información del patrón."
            )

            return {
                "exito": False,
                "respuesta": "ayudar",
                "accion": "preparar_ayuda",
                "contexto": None
            }

        nombre = patron.get(
            "nombre",
            "Aplicación desconocida"
        )

        fallos = patron.get(
            "fallos",
            0
        )

        proceso = patron.get(
            "proceso",
            "Proceso desconocido"
        )

        tipo = patron.get(
            "tipo",
            "problema"
        )

        origen = patron.get(
            "origen",
            "Sistema de patrones"
        )

        contexto = {
            "aplicacion": nombre,
            "problema": (
                "No se pudo confirmar la apertura "
                "de la aplicación."
            ),
            "fallos_consecutivos": fallos,
            "proceso_esperado": proceso,
            "tipo": tipo,
            "origen": origen
        }

        self.ultimo_contexto = contexto

        print()
        print("=" * 60)
        print(" RESPUESTA DE AYUDA")
        print("=" * 60)
        print()

        print("El usuario solicitó ayuda.")
        print()
        print("Contexto preparado para el cerebro:")
        print()

        print("Aplicación:", contexto["aplicacion"])
        print("Problema:", contexto["problema"])
        print(
            "Fallos consecutivos:",
            contexto["fallos_consecutivos"]
        )
        print(
            "Proceso esperado:",
            contexto["proceso_esperado"]
        )
        print("Tipo:", contexto["tipo"])
        print("Origen:", contexto["origen"])

        print()

        return {
            "exito": True,
            "respuesta": "ayudar",
            "accion": "preparar_ayuda",
            "contexto": contexto
        }

    def _procesar_rechazo(self):
        """
        Procesa cuando el usuario selecciona 'Ahora no'.
        """

        self.ultimo_contexto = None

        print()
        print(
            "[RespuestaSugerencia] "
            "El usuario decidió no recibir ayuda ahora."
        )

        return {
            "exito": True,
            "respuesta": "ahora_no",
            "accion": "ninguna",
            "contexto": None
        }

    def obtener_estado(self):
        """
        Devuelve el estado actual del módulo.
        """

        return {
            "ultima_respuesta": self.ultima_respuesta,
            "ultimo_contexto": self.ultimo_contexto
        }


# ============================================================
# PRUEBA INDEPENDIENTE
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print(" PRUEBA DE RESPUESTA DE SUGERENCIA")
    print("=" * 60)
    print()

    gestor = GestorRespuestaSugerencia()

    # --------------------------------------------------------
    # Simulación del patrón detectado
    # --------------------------------------------------------

    patron_prueba = {
        "detectado": True,
        "nombre": "AplicacionDePrueba",
        "fallos": 3,
        "proceso": "proceso_falso_integracion_12345.exe",
        "tipo": "fallo_apertura",
        "origen": "ObservadorPC"
    }

    print("Patrón recibido:")
    print(patron_prueba)

    print()
    print("-" * 60)
    print()

    # --------------------------------------------------------
    # Simulación de 'Ayúdame'
    # --------------------------------------------------------

    resultado = gestor.procesar_respuesta(
        respuesta="ayudar",
        patron=patron_prueba
    )

    print()
    print("-" * 60)
    print()

    print("Resultado final:")
    print(resultado)

    print()
    print("Estado del módulo:")
    print(gestor.obtener_estado())

    print()
    print("=" * 60)
    print(" PRUEBA FINALIZADA")
    print("=" * 60)
    print()

