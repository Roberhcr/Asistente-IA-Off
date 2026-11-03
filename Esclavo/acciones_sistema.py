import ctypes
import datetime
import os
import subprocess
import time


# ============================================================
# BLOQUEAR PANTALLA
# ============================================================

def bloquear_pantalla():

    try:

        ctypes.windll.user32.LockWorkStation()

        return {
            "ok": True,
            "mensaje": "Bloqueando la pantalla."
        }

    except Exception as error:

        return {
            "ok": False,
            "mensaje": f"No pude bloquear la pantalla: {error}"
        }


# ============================================================
# VOLUMEN (usando las teclas multimedia virtuales de Windows)
# ============================================================

VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF


def _pulsar_tecla_multimedia(codigo, repeticiones=1):

    for _ in range(repeticiones):

        ctypes.windll.user32.keybd_event(codigo, 0, 0, 0)
        ctypes.windll.user32.keybd_event(codigo, 0, 2, 0)

        time.sleep(0.05)


def silenciar_volumen():

    try:

        _pulsar_tecla_multimedia(VK_VOLUME_MUTE)

        return {
            "ok": True,
            "mensaje": "Listo, cambié el silencio del volumen."
        }

    except Exception as error:

        return {
            "ok": False,
            "mensaje": f"No pude cambiar el volumen: {error}"
        }


def subir_volumen(pasos=5):

    try:

        _pulsar_tecla_multimedia(VK_VOLUME_UP, pasos)

        return {
            "ok": True,
            "mensaje": "Subiendo el volumen."
        }

    except Exception as error:

        return {
            "ok": False,
            "mensaje": f"No pude subir el volumen: {error}"
        }


def bajar_volumen(pasos=5):

    try:

        _pulsar_tecla_multimedia(VK_VOLUME_DOWN, pasos)

        return {
            "ok": True,
            "mensaje": "Bajando el volumen."
        }

    except Exception as error:

        return {
            "ok": False,
            "mensaje": f"No pude bajar el volumen: {error}"
        }


# ============================================================
# CAPTURA DE PANTALLA
# ============================================================
# Requiere: pip install Pillow

def captura_pantalla():

    try:

        from PIL import ImageGrab

        carpeta_destino = os.path.join(
            os.path.expanduser("~"),
            "Pictures",
            "Screenshots"
        )

        os.makedirs(carpeta_destino, exist_ok=True)

        nombre_archivo = (
            "captura_"
            + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            + ".png"
        )

        ruta = os.path.join(carpeta_destino, nombre_archivo)

        imagen = ImageGrab.grab()
        imagen.save(ruta)

        return {
            "ok": True,
            "mensaje": f"Captura guardada en:\n{ruta}"
        }

    except ImportError:

        return {
            "ok": False,
            "mensaje": (
                "Para tomar capturas necesito la librería "
                "'Pillow'. Instálala con: pip install Pillow"
            )
        }

    except Exception as error:

        return {
            "ok": False,
            "mensaje": f"No pude tomar la captura: {error}"
        }


# ============================================================
# ABRIR EXPLORADOR DE ARCHIVOS
# ============================================================

def abrir_explorador():

    try:

        os.startfile(os.path.expanduser("~"))

        return {
            "ok": True,
            "mensaje": "Abriendo el explorador de archivos."
        }

    except Exception as error:

        return {
            "ok": False,
            "mensaje": f"No pude abrir el explorador: {error}"
        }


# ============================================================
# VACIAR PAPELERA DE RECICLAJE
# ============================================================
# Requiere: pip install winshell pywin32

def vaciar_papelera():

    try:

        import winshell

        winshell.recycle_bin().empty(
            confirm=False,
            show_progress=False,
            sound=False
        )

        return {
            "ok": True,
            "mensaje": "Papelera de reciclaje vaciada."
        }

    except ImportError:

        return {
            "ok": False,
            "mensaje": (
                "Para vaciar la papelera necesito la librería "
                "'winshell'. Instálala con: "
                "pip install winshell pywin32"
            )
        }

    except Exception as error:

        return {
            "ok": False,
            "mensaje": f"No pude vaciar la papelera: {error}"
        }


# ============================================================
# APAGAR / REINICIAR EL EQUIPO
# ============================================================
# Por seguridad, no se ejecutan al instante: Windows da un
# margen de 30 segundos durante el cual se puede cancelar
# diciendo (o escribiendo) "Laura, cancela el apagado".

def apagar_equipo():

    try:

        subprocess.run(["shutdown", "/s", "/t", "30"])

        return {
            "ok": True,
            "mensaje": (
                "El equipo se apagará en 30 segundos. Di "
                "\"Laura, cancela el apagado\" si te "
                "equivocaste."
            )
        }

    except Exception as error:

        return {
            "ok": False,
            "mensaje": f"No pude apagar el equipo: {error}"
        }


def reiniciar_equipo():

    try:

        subprocess.run(["shutdown", "/r", "/t", "30"])

        return {
            "ok": True,
            "mensaje": (
                "El equipo se reiniciará en 30 segundos. Di "
                "\"Laura, cancela el reinicio\" si te "
                "equivocaste."
            )
        }

    except Exception as error:

        return {
            "ok": False,
            "mensaje": f"No pude reiniciar el equipo: {error}"
        }


def cancelar_apagado():

    try:

        subprocess.run(["shutdown", "/a"])

        return {
            "ok": True,
            "mensaje": "Apagado/reinicio cancelado."
        }

    except Exception as error:

        return {
            "ok": False,
            "mensaje": f"No pude cancelar: {error}"
        }


# ============================================================
# MAPA: nombre de acción (de intenciones.py) -> función
# ============================================================

ACCIONES_SISTEMA = {
    "bloquear_pantalla": bloquear_pantalla,
    "silenciar_volumen": silenciar_volumen,
    "subir_volumen": subir_volumen,
    "bajar_volumen": bajar_volumen,
    "captura_pantalla": captura_pantalla,
    "abrir_explorador": abrir_explorador,
    "vaciar_papelera": vaciar_papelera,
    "apagar_equipo": apagar_equipo,
    "reiniciar_equipo": reiniciar_equipo,
    "cancelar_apagado": cancelar_apagado,
}