"""
diagnostico_memoria.py - ¿Quién se está comiendo tu RAM?

Úsalo desde la terminal de VS Code (con o sin Oddye abierto):

    python Config\\diagnostico_memoria.py            -> solo muestra el informe
    python Config\\diagnostico_memoria.py --cerrar   -> además cierra los procesos
                                                de Oddye que quedaron
                                                abiertos sin dueño

El informe muestra:
  1. La RAM total y cuánta está en uso.
  2. Los 15 programas que más memoria gastan (sumando todos sus
     procesos, como hace el Administrador de tareas).
  3. Todo lo relacionado con Oddye y con VS Code, y marca con "SOBRA"
     lo que quedó vivo de ejecuciones anteriores (cerebro, oídos,
     copias de main.py, ventanas web).

Requiere psutil (ya lo usa Oddye).
"""

import os
import sys
import time
import psutil

MB = 1024 * 1024


def memoria_proceso(p):
    """Memoria privada (la que muestra el Administrador de tareas)."""

    try:
        return int(p.memory_full_info().uss // MB)
    except Exception:
        try:
            return int(p.memory_info().rss // MB)
        except Exception:
            return 0


def fmt(mb):

    return f"{mb / 1024:5.2f} GB" if mb >= 1024 else f"{mb:5d} MB"


def leer_procesos():

    procesos = []

    vivos = set(psutil.pids())

    for p in psutil.process_iter(["pid", "ppid", "name", "cmdline", "create_time"]):

        try:

            nombre = (p.info["name"] or "?")

            procesos.append({
                "p": p,
                "pid": p.info["pid"],
                "ppid": p.info["ppid"],
                "nombre": nombre,
                "linea": " ".join(p.info["cmdline"] or []),
                "inicio": p.info["create_time"],
                "mem": memoria_proceso(p),
                "huerfano": p.info["ppid"] not in vivos,
            })

        except Exception:
            continue

    return procesos


def es_de_oddye(proc, carpeta):

    n = proc["nombre"].lower()
    linea = proc["linea"].lower()

    if "llama-server" in n or "whisper-server" in n:
        return "servidor"

    if n.startswith("python") and (
        "main.py" in linea or carpeta.lower() in linea
    ):
        return "python"

    if "msedgewebview2" in n and (
        "python" in linea or "pywebview" in linea
    ):
        return "ventana"

    return None


def main():

    cerrar = "--cerrar" in sys.argv

    carpeta = os.path.basename(os.path.abspath(os.getcwd()))

    vm = psutil.virtual_memory()

    print("=" * 66)
    print(
        f" RAM total: {vm.total / 1024**3:.1f} GB | "
        f"en uso: {vm.percent:.0f} % | "
        f"libre: {vm.available / 1024**3:.1f} GB"
    )
    print("=" * 66)

    print("\nLeyendo procesos (unos segundos)...")

    procesos = leer_procesos()

    # ---------- 1. Los que más gastan, por programa ----------

    grupos = {}

    for pr in procesos:

        g = grupos.setdefault(pr["nombre"].lower(), [0, 0])
        g[0] += pr["mem"]
        g[1] += 1

    print("\n--- Los 15 programas que más memoria usan ---")

    for nombre, (mem, cuantos) in sorted(
        grupos.items(), key=lambda x: -x[1][0]
    )[:15]:

        print(f"  {fmt(mem)}   {nombre}  ({cuantos} proceso{'s' if cuantos != 1 else ''})")

    # ---------- 2. Oddye ----------

    print("\n--- Oddye (cerebro, oídos, copias del programa, ventana) ---")

    de_oddye = []

    for pr in procesos:

        tipo = es_de_oddye(pr, carpeta)

        if tipo:
            de_oddye.append((tipo, pr))

    if not de_oddye:
        print("  No hay nada de Oddye abierto ahora mismo.")

    mios = psutil.Process().pid
    sobran = []

    # Un servidor / copia "sobra" si su padre ya no existe.
    for tipo, pr in sorted(de_oddye, key=lambda x: -x[1]["mem"]):

        if pr["pid"] == mios:
            continue

        antes = time.time() - pr["inicio"]
        horas = antes / 3600

        marca = ""

        if pr["huerfano"] and tipo in ("servidor", "python"):
            marca = "   <-- SOBRA (quedó abierto de antes)"
            sobran.append(pr)

        print(
            f"  {fmt(pr['mem'])}   {pr['nombre']:<22} PID {pr['pid']:<6} "
            f"abierto hace {horas:4.1f} h{marca}"
        )

    # ---------- 3. VS Code ----------

    print("\n--- VS Code y sus ayudantes ---")

    codigo = {"Code (ventanas)": 0, "Pylance / node": 0, "Python": 0, "Otros": 0}

    for pr in procesos:

        n = pr["nombre"].lower()
        linea = pr["linea"].lower()

        if n.startswith("code"):
            codigo["Code (ventanas)"] += pr["mem"]

        elif n.startswith("node") and (
            "pylance" in linea or "server.bundle" in linea
            or "vscode" in linea
        ):
            codigo["Pylance / node"] += pr["mem"]

        elif n.startswith("python") and (
            "vscode" in linea or "jedi" in linea
            or "debugpy" in linea or "pylance" in linea
        ):
            codigo["Python"] += pr["mem"]

    for clave, mem in codigo.items():

        if mem:
            print(f"  {fmt(mem)}   {clave}")

    # ---------- 4. Resumen ----------

    total_sobran = sum(p["mem"] for p in sobran)

    print("\n" + "=" * 66)

    if sobran:

        print(
            f" Procesos de Oddye que SOBRAN: {len(sobran)} "
            f"({fmt(total_sobran).strip()} de RAM)"
        )

        if cerrar:

            print(" Cerrándolos...")

            for pr in sobran:

                try:

                    for hijo in pr["p"].children(recursive=True):
                        hijo.kill()

                    pr["p"].kill()

                    print(f"   cerrado: {pr['nombre']} (PID {pr['pid']})")

                except Exception as error:

                    print(f"   no pude cerrar PID {pr['pid']}: {error}")

        else:

            print(" Para cerrarlos:  python diagnostico_memoria.py --cerrar")

    else:

        print(" No hay procesos de Oddye sobrantes.")

    print("=" * 66)
    print(
        "\nSi sigue gastando mucho, mira arriba la lista de los 15 "
        "programas:\nel que más suma suele ser el culpable."
    )


if __name__ == "__main__":
    main()