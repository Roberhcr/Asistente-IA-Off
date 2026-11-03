import json
import urllib.request
import urllib.error


HOST = "127.0.0.1"
PUERTO = 8080
URL_CHAT = f"http://{HOST}:{PUERTO}/v1/chat/completions"


class CerebroPatrones:

    def __init__(self, host=HOST, puerto=PUERTO):

        self.host = host
        self.puerto = puerto

        self.url_chat = (
            f"http://{self.host}:{self.puerto}/v1/chat/completions"
        )

        self.ultima_respuesta = None
        self.ultimo_contexto = None


    def comprobar_conexion(self):

        url = f"http://{self.host}:{self.puerto}/health"

        try:

            solicitud = urllib.request.Request(
                url,
                method="GET"
            )

            with urllib.request.urlopen(
                solicitud,
                timeout=3
            ) as respuesta:

                if respuesta.status == 200:

                    print(
                        "[CerebroPatrones] Qwen está disponible."
                    )

                    return True

        except Exception as error:

            print(
                "[CerebroPatrones] "
                "No se pudo conectar con Qwen."
            )

            print("Error:", error)

        return False


    def construir_prompt(self, contexto):

        aplicacion = contexto.get(
            "aplicacion",
            "aplicación desconocida"
        )

        problema = contexto.get(
            "problema",
            "problema desconocido"
        )

        fallos = contexto.get(
            "fallos_consecutivos",
            0
        )

        proceso = contexto.get(
            "proceso_esperado",
            "proceso desconocido"
        )

        tipo = contexto.get(
            "tipo",
            "desconocido"
        )

        prompt = (
            "El usuario necesita ayuda con un problema "
            "detectado en su computadora.\n\n"

            f"Aplicación: {aplicacion}\n"
            f"Problema: {problema}\n"
            f"Fallos consecutivos: {fallos}\n"
            f"Proceso esperado: {proceso}\n"
            f"Tipo de problema: {tipo}\n\n"

            "Explica brevemente qué podría estar ocurriendo "
            "y cuál sería la primera comprobación segura "
            "que puede realizar el usuario.\n\n"

            "No ejecutes comandos.\n"
            "No modifiques archivos.\n"
            "Responde únicamente con la respuesta final "
            "para el usuario."
        )

        return prompt


    def consultar(self, contexto):

        if not contexto:

            print(
                "[CerebroPatrones] "
                "No se recibió contexto."
            )

            return None


        self.ultimo_contexto = contexto

        prompt = self.construir_prompt(contexto)


        datos = {

            "messages": [

                {
                    "role": "system",

                    "content": (
                        "Eres un asistente de inteligencia "
                        "artificial local. "

                        "Responde en español. "

                        "Sé breve, claro y directo. "

                        "No muestres razonamientos internos."
                    )
                },

                {
                    "role": "user",

                    "content": prompt
                }

            ],

            "temperature": 0.7,

            "max_tokens": 400,

            "stream": False

        }


        cuerpo = json.dumps(
            datos
        ).encode("utf-8")


        solicitud = urllib.request.Request(

            self.url_chat,

            data=cuerpo,

            headers={
                "Content-Type": "application/json"
            },

            method="POST"
        )


        print()
        print("=" * 60)
        print(" CONSULTANDO AL CEREBRO")
        print("=" * 60)
        print()


        try:

            with urllib.request.urlopen(
                solicitud,
                timeout=180
            ) as respuesta:

                contenido = (
                    respuesta
                    .read()
                    .decode("utf-8")
                )


                datos_respuesta = json.loads(
                    contenido
                )


                # =================================================
                # DIAGNÓSTICO
                # =================================================

                print()
                print("=" * 60)
                print(" RESPUESTA COMPLETA DEL SERVIDOR")
                print("=" * 60)
                print()

                print(
                    json.dumps(
                        datos_respuesta,
                        indent=4,
                        ensure_ascii=False
                    )
                )

                print()


                # =================================================
                # EXTRAER MESSAGE
                # =================================================

                choices = datos_respuesta.get(
                    "choices",
                    []
                )


                if not choices:

                    print(
                        "[CerebroPatrones] "
                        "No existe el campo 'choices'."
                    )

                    return None


                mensaje = choices[0].get(
                    "message",
                    {}
                )


                print("=" * 60)
                print(" CAMPOS DEL MENSAJE")
                print("=" * 60)
                print()

                print(
                    "content:",
                    repr(
                        mensaje.get(
                            "content"
                        )
                    )
                )

                print()

                print(
                    "reasoning_content:",
                    repr(
                        mensaje.get(
                            "reasoning_content"
                        )
                    )
                )

                print()


                # =================================================
                # RESPUESTA FINAL
                # =================================================

                respuesta_qwen = (
                    mensaje
                    .get(
                        "content",
                        ""
                    )
                    or ""
                ).strip()


                self.ultima_respuesta = (
                    respuesta_qwen
                )


                return respuesta_qwen


        except urllib.error.URLError as error:

            print(
                "[CerebroPatrones] "
                "Error de conexión con Qwen."
            )

            print(
                "Error:",
                error
            )


        except json.JSONDecodeError as error:

            print(
                "[CerebroPatrones] "
                "La respuesta no es JSON válido."
            )

            print(
                "Error:",
                error
            )


        except Exception as error:

            print(
                "[CerebroPatrones] "
                "Error inesperado."
            )

            print(
                "Error:",
                error
            )


        return None


    def obtener_estado(self):

        return {

            "host": self.host,

            "puerto": self.puerto,

            "ultima_respuesta": (
                self.ultima_respuesta
            ),

            "ultimo_contexto": (
                self.ultimo_contexto
            )

        }


# =============================================================
# PRUEBA
# =============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print(" PRUEBA DEL CEREBRO DE PATRONES")
    print("=" * 60)
    print()


    cerebro = CerebroPatrones()


    print(
        "Comprobando conexión con llama-server..."
    )

    print()


    if not cerebro.comprobar_conexion():

        print()
        print("=" * 60)
        print(" NO SE PUDO CONECTAR CON EL CEREBRO")
        print("=" * 60)
        print()

        raise SystemExit


    contexto_prueba = {

        "aplicacion": "AplicacionDePrueba",

        "problema": (
            "No se pudo confirmar la apertura "
            "de la aplicación."
        ),

        "fallos_consecutivos": 3,

        "proceso_esperado": (
            "proceso_falso_integracion_12345.exe"
        ),

        "tipo": "fallo_apertura",

        "origen": "ObservadorPC"

    }


    print(
        "Contexto enviado al cerebro:"
    )

    print()

    print(
        json.dumps(
            contexto_prueba,
            indent=4,
            ensure_ascii=False
        )
    )


    respuesta = cerebro.consultar(
        contexto_prueba
    )


    print()
    print("=" * 60)
    print(" RESULTADO")
    print("=" * 60)
    print()


    if respuesta:

        print(
            "RESPUESTA FINAL:"
        )

        print()

        print(
            respuesta
        )

    else:

        print(
            "NO HAY RESPUESTA FINAL EN 'content'."
        )


    print()
    print("=" * 60)
    print(" FIN DE LA PRUEBA")
    print("=" * 60)
    print()
    