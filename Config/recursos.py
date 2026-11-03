"""
recursos.py - Control de memoria y GPU de Oddye

Hace cuatro cosas:

  1. Calcula cómo arrancar el cerebro (llama-server) según TU equipo:
     contexto, buffers y caché, para no pasarse del % de RAM que le
     des (por defecto 50 %). Si hay una GPU dedicada compatible, reparte
     capas del modelo hasta el % de VRAM que le des (por defecto 60 %).
     Si no hay GPU (o es una integrada que comparte la RAM), todo se
     queda en CPU y la RAM se cuida.

  2. Cierra procesos viejos de llama-server / whisper-server que hayan
     quedado vivos de una sesión anterior (cada uno ocupa varios GB).

  3. Hace que esos procesos se cierren solos si Oddye se cierra mal
     (Windows: objeto "Job" con KILL_ON_JOB_CLOSE).

  4. Vigila el consumo, muestra en consola quién gasta cuánto y, si se
     pasa del límite, libera memoria sin quitar funciones.
"""

import os
import re
import gc
import sys
import json
import time
import threading
import subprocess
import urllib.request

try:
    import psutil
except Exception:  # pragma: no cover
    psutil = None

MB = 1024 * 1024

ES_WINDOWS = os.name == "nt"

_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ============================================================
# EQUIPO
# ============================================================

def ram_total_mb():

    if psutil is None:
        return 8192

    return int(psutil.virtual_memory().total // MB)


def ram_disponible_mb():

    if psutil is None:
        return 4096

    return int(psutil.virtual_memory().available // MB)


def _ejecutar(comando, espera=8):

    try:

        salida = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=espera,
            creationflags=_SIN_VENTANA
        )

        return salida.stdout or ""

    except Exception:
        return ""


_INTEGRADAS = re.compile(
    r"intel|uhd|iris|hd graphics|radeon\(tm\) graphics|"
    r"radeon graphics|vega \d|microsoft basic|parsec|virtual",
    re.IGNORECASE
)

_cache_gpu = {}


def detectar_gpu():
    """
    Devuelve {"nombre", "vram_mb", "dedicada"} o None si no hay.
    "dedicada" = tarjeta con memoria propia (NVIDIA / AMD sueltas).
    Una integrada (Intel Iris/UHD, APU) comparte la RAM del sistema:
    usarla no ahorra memoria, así que no se cuenta como GPU útil.
    """

    if "gpu" in _cache_gpu:
        return _cache_gpu["gpu"]

    gpu = None

    # NVIDIA: nvidia-smi da la VRAM exacta.
    salida = _ejecutar([
        "nvidia-smi",
        "--query-gpu=name,memory.total",
        "--format=csv,noheader,nounits"
    ])

    for linea in salida.splitlines():

        partes = [p.strip() for p in linea.split(",")]

        if len(partes) >= 2 and partes[1].isdigit():

            gpu = {
                "nombre": partes[0],
                "vram_mb": int(partes[1]),
                "dedicada": True
            }

            break

    # Cualquier otra: preguntarle a Windows.
    if gpu is None and ES_WINDOWS:

        salida = _ejecutar([
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_VideoController | "
            "Select-Object Name,AdapterRAM | ConvertTo-Json -Compress"
        ], espera=12)

        try:

            datos = json.loads(salida) if salida.strip() else []

            if isinstance(datos, dict):
                datos = [datos]

            mejor = None

            for d in datos:

                nombre = str(d.get("Name") or "")
                ram = int((d.get("AdapterRAM") or 0) // MB)
                integrada = bool(_INTEGRADAS.search(nombre))

                candidato = {
                    "nombre": nombre,
                    "vram_mb": ram,
                    "dedicada": not integrada
                }

                # Prefiere una dedicada sobre una integrada.
                if mejor is None or (
                    candidato["dedicada"] and not mejor["dedicada"]
                ):
                    mejor = candidato

            gpu = mejor

        except Exception:
            gpu = None

    _cache_gpu["gpu"] = gpu

    return gpu


def llama_soporta_gpu(llama_exe):
    """¿Este llama-server trae soporte de GPU (CUDA / Vulkan / HIP / SYCL)?"""

    carpeta = os.path.dirname(llama_exe)

    nombre = (llama_exe + " " + carpeta).lower()

    if re.search(r"cuda|vulkan|hip|sycl|metal", nombre):
        return True

    try:

        for archivo in os.listdir(carpeta):

            if re.match(
                r"ggml-(cuda|vulkan|hip|sycl)",
                archivo,
                re.IGNORECASE
            ):
                return True

    except Exception:
        pass

    return False


# ============================================================
# PLAN DEL CEREBRO
# ============================================================

# Qwen3-4B: 36 capas, 8 cabezas KV de 128 -> con caché q4_0 son
# ~41 KB por token de contexto.
_CAPAS_MODELO = 36
_KB_POR_TOKEN_KV = 41

# Lo que gasta el resto de la app (Whisper, Piper, Python, ventana).
_RESTO_APP_MB = 1500


def planificar_cerebro(
    modelo,
    llama_exe,
    ctx_deseado=4096,
    ram_pct=50,
    gpu_pct=60
):
    """
    Devuelve un plan: ctx, batch, ubatch, capas_gpu y notas.
    """

    total = ram_total_mb()
    presupuesto = int(total * ram_pct / 100)

    try:
        modelo_mb = int(os.path.getsize(modelo) // MB)
    except Exception:
        modelo_mb = 2600

    gpu = detectar_gpu()

    usa_gpu = bool(
        gpu
        and gpu["dedicada"]
        and gpu["vram_mb"] >= 2048
        and llama_soporta_gpu(llama_exe)
    )

    notas = []

    # ---------- GPU ----------

    capas_gpu = 0

    if usa_gpu:

        vram = int(gpu["vram_mb"] * gpu_pct / 100)

        kv = int(ctx_deseado * _KB_POR_TOKEN_KV / 1024)

        por_capa = max(1.0, modelo_mb / _CAPAS_MODELO)

        libre = vram - kv - 300

        capas_gpu = max(0, min(_CAPAS_MODELO + 1, int(libre / por_capa)))

        if capas_gpu >= _CAPAS_MODELO:
            capas_gpu = 99

        notas.append(
            f"GPU {gpu['nombre']}: {capas_gpu} capas "
            f"(hasta {gpu_pct} % de {gpu['vram_mb']} MB)"
        )

    elif gpu and not gpu["dedicada"]:

        notas.append(
            f"GPU integrada ({gpu['nombre']}): comparte la RAM, "
            "no se usa; todo va por CPU"
        )

    else:

        notas.append("Sin GPU compatible: todo va por CPU")

    # ---------- RAM ----------

    en_ram = modelo_mb if capas_gpu == 0 else int(
        modelo_mb * max(0, _CAPAS_MODELO - capas_gpu) / _CAPAS_MODELO
    )

    ctx = int(ctx_deseado)

    def estimado(c):
        return int(en_ram * 1.05 + c * _KB_POR_TOKEN_KV / 1024 + 400
                   + _RESTO_APP_MB)

    while ctx > 2048 and estimado(ctx) > presupuesto:
        ctx -= 512

    if ctx != ctx_deseado:

        notas.append(
            f"Contexto reducido a {ctx} para caber en "
            f"{ram_pct} % de la RAM"
        )

    # Con poca RAM, buffers más pequeños.
    justo = estimado(ctx) > presupuesto * 0.8

    return {
        "ctx": ctx,
        "batch": 256 if justo else 512,
        "ubatch": 128 if justo else 256,
        "capas_gpu": capas_gpu,
        "presupuesto_mb": presupuesto,
        "ram_total_mb": total,
        "estimado_mb": estimado(ctx),
        "modelo_mb": modelo_mb,
        "notas": notas,
    }


def comandos_llama(llama_exe, modelo, plan, hilos, puerto=8080):
    """
    Lista de comandos a probar, del más optimizado al original.
    Si una versión de llama-server no entiende un parámetro y se cierra,
    se pasa al siguiente.
    """

    base = [
        llama_exe,
        "-m", modelo,
        "--port", str(puerto),
        "--ctx-size", str(plan["ctx"]),
        "--cache-type-k", "q4_0",
        "--cache-type-v", "q4_0",
        "--threads", str(hilos),
    ]

    gpu = ["-ngl", str(plan["capas_gpu"])] if plan["capas_gpu"] else []

    optimizado = base + gpu + [
        # Un solo usuario: toda la memoria de contexto para una
        # conversación (con varios "slots" se reparte y se desperdicia).
        "--parallel", "1",
        # Las versiones nuevas guardan hasta 8 GB de RAM de caché de
        # prompts; aquí no hace falta.
        "--cache-ram", "0",
        "--batch-size", str(plan["batch"]),
        "--ubatch-size", str(plan["ubatch"]),
    ]

    intermedio = base + gpu + ["--parallel", "1"]

    return [optimizado, intermedio, base]


# ============================================================
# PROCESOS VIEJOS
# ============================================================

def _ancestros_y_propios():

    pids = {os.getpid()}

    try:

        yo = psutil.Process()

        pids |= {h.pid for h in yo.children(recursive=True)}
        pids |= {a.pid for a in yo.parents()}

    except Exception:
        pass

    return pids


def limpiar_huerfanos(rutas_exe, claves=()):
    """
    Cierra llama-server / whisper-server que sigan vivos de una sesión
    anterior (cada uno ocupa varios GB). Se reconocen por la ruta del
    .exe o porque su línea de comandos nombra tus modelos.
    Devuelve cuántos cerró.
    """

    if psutil is None:
        return 0

    objetivos = {
        os.path.normcase(os.path.abspath(r)) for r in rutas_exe if r
    }

    claves = [c.lower() for c in claves if c]

    propios = _ancestros_y_propios()

    cerrados = 0

    for p in psutil.process_iter(["pid", "name", "exe", "cmdline"]):

        try:

            if p.info["pid"] in propios:
                continue

            exe = p.info.get("exe") or ""
            nombre = (p.info.get("name") or "").lower()

            coincide = bool(exe) and (
                os.path.normcase(os.path.abspath(exe)) in objetivos
            )

            if not coincide and (
                "llama-server" in nombre or "whisper-server" in nombre
            ):

                linea = " ".join(p.info.get("cmdline") or []).lower()

                coincide = any(c in linea for c in claves)

            if coincide:

                p.kill()
                cerrados += 1

        except Exception:
            continue

    return cerrados


def cerrar_instancias_viejas(script):
    """
    Si quedó otra copia de Oddye (main.py) viva de antes —por ejemplo
    sin ventana, tras detener la ejecución desde VS Code— la cierra
    junto con todo lo que abrió. Devuelve cuántas cerró.
    """

    if psutil is None:
        return 0

    objetivo = os.path.normcase(os.path.abspath(script))

    propios = _ancestros_y_propios()

    cerradas = 0

    for p in psutil.process_iter(["pid", "name", "cmdline"]):

        try:

            if p.info["pid"] in propios:
                continue

            if not (p.info.get("name") or "").lower().startswith("python"):
                continue

            linea = p.info.get("cmdline") or []

            if not any(
                os.path.normcase(os.path.abspath(a)) == objetivo
                for a in linea[1:] if a and not a.startswith("-")
            ):
                continue

            hijos = p.children(recursive=True)

            for h in hijos:

                try:
                    h.kill()
                except Exception:
                    pass

            p.kill()

            cerradas += 1

        except Exception:
            continue

    return cerradas


# ============================================================
# QUE LOS HIJOS MUERAN CON Oddye (Windows)
# ============================================================

class JobHijos:

    def __init__(self):

        self._h = None
        self._agregados = set()

        if not ES_WINDOWS:
            return

        try:

            import ctypes
            from ctypes import wintypes

            class BASIC(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]

            class IO(ctypes.Structure):
                _fields_ = [(n, ctypes.c_uint64) for n in (
                    "ReadOperationCount", "WriteOperationCount",
                    "OtherOperationCount", "ReadTransferCount",
                    "WriteTransferCount", "OtherTransferCount")]

            class EXT(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", BASIC),
                    ("IoInfo", IO),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]

            k32 = ctypes.windll.kernel32
            k32.CreateJobObjectW.restype = wintypes.HANDLE

            h = k32.CreateJobObjectW(None, None)

            info = EXT()
            info.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE

            ok = k32.SetInformationJobObject(
                h, 9, ctypes.byref(info), ctypes.sizeof(info)
            )

            if ok:
                self._h = h
                self._k32 = k32

        except Exception as error:

            print(f"[Memoria] No se pudo crear el grupo de procesos: {error}")


    def agregar(self, pid):

        if self._h is None or pid in self._agregados:
            return

        self._agregados.add(pid)

        try:

            import ctypes
            from ctypes import wintypes

            k32 = self._k32
            k32.OpenProcess.restype = wintypes.HANDLE

            # PROCESS_SET_QUOTA | PROCESS_TERMINATE
            hp = k32.OpenProcess(0x0100 | 0x0001, False, pid)

            if hp:
                k32.AssignProcessToJobObject(self._h, hp)
                k32.CloseHandle(hp)

        except Exception:
            pass


# ============================================================
# VIGILANTE DE MEMORIA
# ============================================================

_ROLES = (
    ("llama-server", "cerebro"),
    ("whisper-server", "oídos"),
    ("msedgewebview2", "ventana"),
)


def _rol(nombre, es_propio):

    if es_propio:
        return "python"

    n = (nombre or "").lower()

    for clave, rol in _ROLES:
        if clave in n:
            return rol

    return "otros"


def recortar_working_set(pid):
    """Pide a Windows que devuelva a disco lo que el proceso no usa ya."""

    if not ES_WINDOWS:
        return False

    try:

        import ctypes
        from ctypes import wintypes

        k32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi

        k32.OpenProcess.restype = wintypes.HANDLE

        # PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA
        h = k32.OpenProcess(0x0400 | 0x0100, False, pid)

        if not h:
            return False

        ok = psapi.EmptyWorkingSet(h)

        k32.CloseHandle(h)

        return bool(ok)

    except Exception:
        return False


class VigilanteMemoria:

    def __init__(
        self,
        presupuesto_mb,
        ocupada=None,
        liberar_cerebro=None,
        intervalo=15,
        reposo_seg=45,
        log_ruta=None
    ):

        self.presupuesto_mb = presupuesto_mb
        self._ocupada = ocupada or (lambda: False)
        self._liberar_cerebro = liberar_cerebro
        self.intervalo = intervalo
        self.reposo_seg = reposo_seg
        self.log_ruta = log_ruta

        self.job = JobHijos()

        self._activo = False
        self._hilo = None

        self._inactivo_desde = time.time()
        self._ultimo_aviso = 0.0
        self._ultimo_recorte = 0.0
        self._ultimo_total = 0

        self.ultima_medida = {}


    # --------------------------------------------------------

    def iniciar(self):

        if self._activo or psutil is None:
            return

        self._activo = True

        self._hilo = threading.Thread(target=self._bucle, daemon=True)
        self._hilo.start()


    def detener(self):
        self._activo = False


    def medir(self):

        yo = psutil.Process()

        procesos = [(yo, True)]

        try:
            procesos += [
                (h, False) for h in yo.children(recursive=True)
            ]
        except Exception:
            pass

        por_rol = {}
        pids = {}

        for p, propio in procesos:

            try:

                nombre = p.name()
                mem = p.memory_info()
                rss = int(mem.rss // MB)

            except Exception:
                continue

            rol = _rol(nombre, propio)

            por_rol[rol] = por_rol.get(rol, 0) + rss
            pids.setdefault(rol, []).append(p.pid)

            # Todo hijo muere si Oddye se cierra mal.
            if not propio:
                self.job.agregar(p.pid)

        total = sum(por_rol.values())

        self.ultima_medida = {
            "total_mb": total,
            "limite_mb": self.presupuesto_mb,
            "por_proceso_mb": por_rol,
            "ram_libre_mb": ram_disponible_mb(),
        }

        self._pids = pids

        return self.ultima_medida


    # --------------------------------------------------------

    def _bucle(self):

        while self._activo:

            try:
                self._ciclo()
            except Exception as error:
                print(f"[Memoria] Error: {error}")

            time.sleep(self.intervalo)


    def _ciclo(self):

        m = self.medir()

        total = m["total_mb"]
        ahora = time.time()

        ocupada = bool(self._ocupada())

        if ocupada:
            self._inactivo_desde = ahora

        en_reposo = (ahora - self._inactivo_desde) >= self.reposo_seg

        # ---- Informe en consola (solo si cambió o pasó un rato) ----
        cambio = abs(total - self._ultimo_total) > max(150, total * 0.1)

        if cambio or ahora - self._ultimo_aviso > 300:

            self._ultimo_aviso = ahora
            self._ultimo_total = total

            self._informar(m)

        # ---- En reposo: devolver lo que no se usa ----
        if en_reposo and ahora - self._ultimo_recorte > 60:

            self._ultimo_recorte = ahora

            for rol in ("python", "ventana", "oídos"):

                for pid in self._pids.get(rol, []):
                    recortar_working_set(pid)

        # ---- Pasó del límite ----
        if total > self.presupuesto_mb:

            if self._liberar_cerebro is not None and not ocupada:

                try:
                    self._liberar_cerebro()
                except Exception:
                    pass

            gc.collect()

            if not ocupada:

                for rol, pids in self._pids.items():

                    for pid in pids:
                        recortar_working_set(pid)

            nuevo = self.medir()["total_mb"]

            print(
                f"[Memoria] Pasó del límite ({total} MB > "
                f"{self.presupuesto_mb} MB). Liberé hasta {nuevo} MB."
            )


    def _informar(self, m):

        partes = " | ".join(
            f"{rol} {mb / 1024:.2f} GB"
            for rol, mb in sorted(
                m["por_proceso_mb"].items(),
                key=lambda x: -x[1]
            )
        )

        linea = (
            f"[Memoria] Total {m['total_mb'] / 1024:.1f} GB de "
            f"{m['limite_mb'] / 1024:.1f} GB permitidos  ->  {partes}"
        )

        print(linea)

        if self.log_ruta:

            try:

                if (
                    os.path.isfile(self.log_ruta)
                    and os.path.getsize(self.log_ruta) > 200_000
                ):
                    os.replace(self.log_ruta, self.log_ruta + ".viejo")

                with open(self.log_ruta, "a", encoding="utf-8") as f:
                    f.write(time.strftime("%H:%M:%S ") + linea + "\n")

            except Exception:
                pass


def borrar_cache_llama(url="http://127.0.0.1:8080", slot=0):
    """Vacía la caché de prompts de llama-server (libera RAM)."""

    try:

        solicitud = urllib.request.Request(
            f"{url}/slots/{slot}?action=erase",
            data=b"",
            method="POST"
        )

        urllib.request.urlopen(solicitud, timeout=3).read()

        return True

    except Exception:
        return False