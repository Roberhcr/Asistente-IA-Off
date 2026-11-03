"""
chats.py - Guardado de conversaciones de Oddye

Cada chat es un archivo JSON dentro de la carpeta Chats/:

    {
        "id": "20261018-231700-a1b2c3",
        "titulo": "Ayúdame con mi tarea de historia",
        "creado": 1789999999.0,
        "actualizado": 1789999999.0,
        "mensajes": [
            {"role": "user", "content": "...", "ts": 1789999999.0, "ctx": true},
            {"role": "assistant", "content": "...", "ts": ..., "ctx": true}
        ]
    }

"ctx" indica si el mensaje pasó por Qwen. Solo esos mensajes se le
devuelven a Qwen como contexto al reabrir el chat (los comandos como
"abre Word" se muestran en pantalla pero no ensucian el contexto).
"""

import os
import re
import json
import time
import uuid
import datetime
import threading
import unicodedata


_RE_ID = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{6}$")


def _normalizar(texto):

    texto = unicodedata.normalize("NFD", (texto or "").lower())

    return "".join(
        c for c in texto
        if unicodedata.category(c) != "Mn"
    )


def titulo_desde(texto):

    t = re.sub(r"\s+", " ", (texto or "").strip())

    if not t:
        return "Nuevo chat"

    if len(t) > 48:
        t = t[:47].rstrip() + "…"

    return t[0].upper() + t[1:]


class GestorChats:

    def __init__(self, carpeta):

        self.carpeta = carpeta

        self._lock = threading.RLock()

        os.makedirs(self.carpeta, exist_ok=True)


    # --------------------------------------------------------
    # Utilidades internas
    # --------------------------------------------------------

    def _ruta(self, chat_id):

        if not isinstance(chat_id, str) or not _RE_ID.match(chat_id):
            return None

        return os.path.join(self.carpeta, chat_id + ".json")


    def _leer(self, chat_id):

        ruta = self._ruta(chat_id)

        if ruta is None or not os.path.isfile(ruta):
            return None

        try:

            with open(ruta, "r", encoding="utf-8") as archivo:
                datos = json.load(archivo)

            if not isinstance(datos, dict):
                return None

            datos.setdefault("id", chat_id)
            datos.setdefault("titulo", "Nuevo chat")
            datos.setdefault("creado", 0)
            datos.setdefault("actualizado", datos["creado"])

            if not isinstance(datos.get("mensajes"), list):
                datos["mensajes"] = []

            return datos

        except Exception as error:

            print(f"[Chats] No se pudo leer {chat_id}: {error}")

            return None


    def _escribir(self, chat):

        ruta = self._ruta(chat["id"])

        if ruta is None:
            raise ValueError("Id de chat inválido.")

        temporal = ruta + ".tmp"

        with open(temporal, "w", encoding="utf-8") as archivo:

            json.dump(
                chat,
                archivo,
                ensure_ascii=False,
                indent=2
            )

        os.replace(temporal, ruta)


    # --------------------------------------------------------
    # API
    # --------------------------------------------------------

    def crear(self, primer_texto=""):

        ahora = time.time()

        chat_id = (
            datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            + "-"
            + uuid.uuid4().hex[:6]
        )

        chat = {
            "id": chat_id,
            "titulo": titulo_desde(primer_texto),
            "creado": ahora,
            "actualizado": ahora,
            "mensajes": []
        }

        with self._lock:
            self._escribir(chat)

        return chat_id


    def agregar(self, chat_id, mensajes):

        with self._lock:

            chat = self._leer(chat_id)

            if chat is None:
                return False

            ahora = time.time()

            for m in mensajes:

                chat["mensajes"].append({
                    "role": m["role"],
                    "content": m["content"],
                    "ts": ahora,
                    "ctx": bool(m.get("ctx", True))
                })

            chat["actualizado"] = ahora

            self._escribir(chat)

        return True


    def obtener(self, chat_id):

        with self._lock:
            return self._leer(chat_id)


    def listar(self, filtro=""):

        filtro_n = _normalizar(filtro).strip()

        resultado = []

        with self._lock:

            try:
                nombres = os.listdir(self.carpeta)
            except Exception:
                return []

            for nombre in nombres:

                if not nombre.endswith(".json"):
                    continue

                chat = self._leer(nombre[:-5])

                if chat is None:
                    continue

                if filtro_n:

                    en_titulo = filtro_n in _normalizar(chat["titulo"])

                    en_mensajes = any(
                        filtro_n in _normalizar(m.get("content", ""))
                        for m in chat["mensajes"]
                    )

                    if not (en_titulo or en_mensajes):
                        continue

                resultado.append({
                    "id": chat["id"],
                    "titulo": chat["titulo"],
                    "creado": chat["creado"],
                    "actualizado": chat["actualizado"],
                    "total": len(chat["mensajes"])
                })

        resultado.sort(
            key=lambda c: c["actualizado"],
            reverse=True
        )

        return resultado


    def renombrar(self, chat_id, titulo):

        titulo = re.sub(r"\s+", " ", (titulo or "").strip())

        if not titulo:
            return False

        if len(titulo) > 80:
            titulo = titulo[:79].rstrip() + "…"

        with self._lock:

            chat = self._leer(chat_id)

            if chat is None:
                return False

            chat["titulo"] = titulo

            self._escribir(chat)

        return True


    def borrar(self, chat_id):

        ruta = self._ruta(chat_id)

        if ruta is None:
            return False

        with self._lock:

            try:
                os.remove(ruta)
                return True
            except FileNotFoundError:
                return False
            except Exception as error:
                print(f"[Chats] No se pudo borrar {chat_id}: {error}")
                return False