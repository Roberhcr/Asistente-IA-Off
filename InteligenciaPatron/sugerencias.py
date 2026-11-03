
import random
import time
import threading

from notificaciones import GestorNotificaciones


# ============================================================
# CONFIGURACIÓN
# ============================================================

INTERVALO_MINIMO = 10  * 25
INTERVALO_MAXIMO = 20  *  40

INTERVALO_IGNORADO_MINIMO = 20 * 60
INTERVALO_IGNORADO_MAXIMO = 40 * 60

INTERVALO_MUY_IGNORADO_MINIMO = 40 * 60
INTERVALO_MUY_IGNORADO_MAXIMO = 60 * 60

IGNORACIONES_PARA_AUMENTAR = 3


# ============================================================
# PRIORIDADES
# ============================================================

PRIORIDAD_PROBLEMA = 100
PRIORIDAD_CONTEXTO = 60
PRIORIDAD_GENERAL = 30
PRIORIDAD_ALEATORIA = 10


class GestorSugerencias:

    def __init__(self, gestor_notificaciones=None):

        self._lock = threading.Lock()

        self.ultima_sugerencia = time.time()

        self.ignoraciones = 0

        self.sugerencias_mostradas = 0
        self.sugerencias_aceptadas = 0
        self.sugerencias_rechazadas = 0

        # ----------------------------------------------------
        # Gestor de notificaciones
        # ----------------------------------------------------

        if gestor_notificaciones is None:
            self.notificaciones = GestorNotificaciones()
        else:
            self.notificaciones = gestor_notificaciones

        self._programar_siguiente()


    # ========================================================
    # PROGRAMACIÓN
    # ========================================================

    def _programar_siguiente(self):

        if self.ignoraciones >= IGNORACIONES_PARA_AUMENTAR * 2:

            minimo = INTERVALO_MUY_IGNORADO_MINIMO
            maximo = INTERVALO_MUY_IGNORADO_MAXIMO

        elif self.ignoraciones >= IGNORACIONES_PARA_AUMENTAR:

            minimo = INTERVALO_IGNORADO_MINIMO
            maximo = INTERVALO_IGNORADO_MAXIMO

        else:

            minimo = INTERVALO_MINIMO
            maximo = INTERVALO_MAXIMO

        self.proximo_intervalo = random.randint(
            minimo,
            maximo
        )

        self.proxima_sugerencia = (
            time.time() + self.proximo_intervalo
        )


    # ========================================================
    # COMPROBAR SI PUEDE SUGERIR
    # ========================================================

    def puede_sugerir(self):

        with self._lock:

            return (
                time.time() >= self.proxima_sugerencia
            )


    # ========================================================
    # MOSTRAR SUGERENCIA
    # ========================================================

    def mostrar_sugerencia(
        self,
        mensaje,
        tipo="general",
        titulo="Asistente IA",
        callback_externo=None
    ):

        with self._lock:

            self.ultima_sugerencia = time.time()

            self.sugerencias_mostradas += 1

            self._programar_siguiente()


        # ----------------------------------------------------
        # Callback interno
        #
        # Se mantiene para que GestorSugerencias continúe
        # registrando estadísticas.
        # ----------------------------------------------------

        def respuesta_usuario(respuesta):

            # ----------------------------------------------
            # Registrar aceptación
            # ----------------------------------------------

            if respuesta == "ayudar":

                self.registrar_aceptacion()


            # ----------------------------------------------
            # Registrar rechazo
            # ----------------------------------------------

            elif respuesta == "ahora_no":

                self.registrar_rechazo()


            # ----------------------------------------------
            # Avisar al sistema externo
            # ----------------------------------------------

            if callback_externo is not None:

                try:

                    callback_externo(respuesta)

                except Exception as error:

                    print(
                        "[Sugerencias] Error en callback externo:"
                    )

                    print(error)


        # ----------------------------------------------------
        # Mostrar notificación
        # ----------------------------------------------------

        return self.notificaciones.mostrar(

            mensaje=mensaje,

            titulo=titulo,

            tipo=tipo,

            callback=respuesta_usuario
        )


    # ========================================================
    # REGISTRAR ACEPTACIÓN
    # ========================================================

    def registrar_aceptacion(self):

        with self._lock:

            self.sugerencias_aceptadas += 1

            if self.ignoraciones > 0:

                self.ignoraciones -= 1


        print(
            "[Sugerencias] Usuario aceptó la sugerencia."
        )


    # ========================================================
    # REGISTRAR RECHAZO
    # ========================================================

    def registrar_rechazo(self):

        with self._lock:

            self.sugerencias_rechazadas += 1

            self.ignoraciones += 1


        print(
            "[Sugerencias] Usuario ignoró la sugerencia."
        )


    # ========================================================
    # TIEMPO RESTANTE
    # ========================================================

    def segundos_restantes(self):

        with self._lock:

            restante = (
                self.proxima_sugerencia -
                time.time()
            )

            return max(
                0,
                int(restante)
            )


    def minutos_restantes(self):

        segundos = self.segundos_restantes()

        return round(
            segundos / 60,
            1
        )


    # ========================================================
    # ESTADO
    # ========================================================

    def obtener_estado(self):

        with self._lock:

            return {

                "ultima_sugerencia":
                    self.ultima_sugerencia,

                "proxima_sugerencia":
                    self.proxima_sugerencia,

                "segundos_restantes":
                    max(
                        0,
                        int(
                            self.proxima_sugerencia -
                            time.time()
                        )
                    ),

                "intervalo_actual":
                    self.proximo_intervalo,

                "ignoraciones":
                    self.ignoraciones,

                "sugerencias_mostradas":
                    self.sugerencias_mostradas,

                "sugerencias_aceptadas":
                    self.sugerencias_aceptadas,

                "sugerencias_rechazadas":
                    self.sugerencias_rechazadas
            }


    # ========================================================
    # SELECCIÓN DE TIPO
    # ========================================================

    def seleccionar_tipo(
        self,
        problema=False,
        contexto=False
    ):

        if problema:

            return {
                "tipo": "problema",
                "prioridad": PRIORIDAD_PROBLEMA
            }

        if contexto:

            return {
                "tipo": "contexto",
                "prioridad": PRIORIDAD_CONTEXTO
            }

        numero = random.randint(
            1,
            100
        )

        if numero <= 50:

            tipo = "general"
            prioridad = PRIORIDAD_GENERAL

        else:

            tipo = "aleatoria"
            prioridad = PRIORIDAD_ALEATORIA

        return {
            "tipo": tipo,
            "prioridad": prioridad
        }


# ============================================================
# PRUEBA
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print(" PRUEBA SUGERENCIAS + NOTIFICACIONES")
    print("=" * 60)
    print()

    gestor = GestorSugerencias()

    print(
        "Sistema de sugerencias creado correctamente."
    )

    print()

    estado = gestor.obtener_estado()

    print(
        "Intervalo programado:",
        estado["intervalo_actual"],
        "segundos"
    )

    print(
        "Tiempo restante:",
        estado["segundos_restantes"],
        "segundos"
    )

    print()

    print(
        "Mostrando sugerencia de prueba..."
    )

    def respuesta_prueba(respuesta):

        print()
        print(
            "[PRUEBA] Respuesta recibida:",
            respuesta
        )

    gestor.mostrar_sugerencia(

        mensaje=(
            "He detectado algo que podría "
            "necesitar tu atención.\n\n"
            "¿Quieres que te ayude?"
        ),

        tipo="problema",

        titulo="Asistente IA",

        callback_externo=respuesta_prueba
    )

    print()

    print(
        "Esperando respuesta del usuario..."
    )

    print()

    time.sleep(2)

    print()
    print("=" * 60)
    print(" ESTADO FINAL")
    print("=" * 60)
    print()

    estado = gestor.obtener_estado()

    print(
        "Sugerencias mostradas:",
        estado["sugerencias_mostradas"]
    )

    print(
        "Aceptadas:",
        estado["sugerencias_aceptadas"]
    )

    print(
        "Rechazadas:",
        estado["sugerencias_rechazadas"]
    )

    print(
        "Ignoraciones:",
        estado["ignoraciones"]
    )

    print()

