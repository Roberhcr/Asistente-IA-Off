from win11toast import toast


class GestorNotificaciones:

    def __init__(self):
        self.notificacion_activa = False


    # =========================================================
    # MOSTRAR NOTIFICACIÓN
    # =========================================================

    def mostrar(
        self,
        mensaje,
        titulo="Asistente IA",
        tipo="general",
        callback=None,
        esperar_respuesta=False
    ):

        self.notificacion_activa = True

        print("\n[Notificaciones] Mostrando notificación de Windows...")
        print(f"[Notificaciones] Título: {titulo}")
        print(f"[Notificaciones] Tipo: {tipo}")

        # =====================================================
        # CALLBACK INTERNO
        # =====================================================

        def procesar_respuesta(resultado):

            self.notificacion_activa = False

            print(
                "[Notificaciones] Respuesta recibida:"
            )

            print(
                resultado
            )

            # ---------------------------------------------
            # Si "resultado" es un diccionario, hubo un clic
            # real (en un botón o en el cuerpo de la
            # notificación). Si NO es un diccionario (es una
            # tupla), fue un cierre por tiempo o el usuario
            # la descartó sin tocarla.
            #
            # NOTA: en muchos equipos, Windows no dibuja los
            # botones "Ayúdame"/"Ahora no" de scripts de
            # Python normales (limitación del sistema, no del
            # código). Por eso, cualquier clic real sobre la
            # notificación se trata como "Ayúdame", salvo que
            # el botón "Ahora no" sí llegue a marcarse.
            # ---------------------------------------------

            if isinstance(resultado, dict):

                argumento = resultado.get(
                    "arguments",
                    ""
                )

                # ---------------------------------------------
                # AHORA NO (solo si el botón sí llega a marcarlo)
                # ---------------------------------------------

                if argumento == "ahora_no":

                    print(
                        "[Notificaciones] Usuario eligió: Ahora no"
                    )

                    if callback is not None:

                        try:
                            callback("ahora_no")

                        except Exception as error:

                            print(
                                "[Notificaciones] Error en callback:"
                            )

                            print(error)

                    return


                # ---------------------------------------------
                # CUALQUIER OTRO CLIC (botón "Ayúdame" o el
                # cuerpo de la notificación) cuenta como Ayúdame.
                # ---------------------------------------------

                print(
                    "[Notificaciones] Usuario eligió: Ayúdame "
                    "(clic en la notificación)"
                )

                if callback is not None:

                    try:
                        callback("ayudar")

                    except Exception as error:

                        print(
                            "[Notificaciones] Error en callback:"
                        )

                        print(error)

                return


            # ---------------------------------------------
            # La notificación se cerró sola (tiempo agotado
            # o descartada), sin que el usuario la tocara.
            # ---------------------------------------------

            print(
                "[Notificaciones] La notificación se cerró "
                "sin interacción."
            )


        # =====================================================
        # BOTONES
        # =====================================================

        botones = [

            {
                "activationType": "foreground",
                "arguments": "ayudar",
                "content": "Ayúdame"
            },

            {
                "activationType": "foreground",
                "arguments": "ahora_no",
                "content": "Ahora no"
            }

        ]


        # =====================================================
        # MOSTRAR TOAST DE WINDOWS
        # =====================================================

        try:

            # ---------------------------------------------
            # IMPORTANTE: NO volver a llamar aquí a
            # procesar_respuesta() con lo que devuelva
            # toast(). on_click ya se encarga de procesar
            # la respuesta exactamente una vez; procesarla
            # otra vez con el valor de retorno duplicaba
            # el mensaje enviado a Qwen y dejaba el estado
            # interno inconsistente para la siguiente
            # notificación.
            # ---------------------------------------------

            toast(

                mensaje,

                titulo,

                buttons=botones,

                on_click=procesar_respuesta,

                app_id="IA Offline"

            )


        except Exception as error:

            self.notificacion_activa = False

            print(
                "\n[Notificaciones] ERROR AL MOSTRAR "
                "LA NOTIFICACIÓN:"
            )

            print(error)


        return True


    # =========================================================
    # CERRAR / REINICIAR ESTADO
    # =========================================================

    def limpiar(self):

        self.notificacion_activa = False


    # =========================================================
    # ESTADO
    # =========================================================

    def esta_activa(self):

        return self.notificacion_activa


# =============================================================
# PRUEBA DIRECTA
# =============================================================

if __name__ == "__main__":

    gestor = GestorNotificaciones()


    def respuesta_prueba(respuesta):

        print("\n========================================")
        print("RESPUESTA DE PRUEBA")
        print("========================================")

        print(
            "Respuesta:",
            respuesta
        )

        if respuesta == "ayudar":

            print(
                "✓ El botón AYÚDAME funciona."
            )

        elif respuesta == "ahora_no":

            print(
                "✓ El botón AHORA NO funciona."
            )

        print()


    print("\n========================================")
    print("   PRUEBA DE NOTIFICACIONES WINDOWS 11")
    print("========================================")


    gestor.mostrar(

        mensaje=(
            "Esta es una prueba del sistema de "
            "sugerencias de tu asistente IA."
        ),

        titulo="Asistente IA",

        tipo="prueba",

        callback=respuesta_prueba
    )


    print(
        "\nLa notificación fue enviada a Windows 11."
    )

    print(
        "Selecciona uno de los botones en la notificación."
    )

    print()