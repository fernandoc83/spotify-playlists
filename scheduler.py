#!/usr/bin/env python3
"""
Scheduler semanal para regenerar las playlists dentro de Docker.

Duerme hasta el próximo día/hora configurado, corre `playlists.py`, y repite.
No usa cron ni dependencias extra: solo stdlib.

Config por variables de entorno (todas opcionales):
    DIA_SEMANA    día de la semana, 0=lunes … 6=domingo   (default 0 = lunes)
    HORA          hora del día 0-23                        (default 9)
    MINUTO        minuto 0-59                              (default 0)
    RUN_ON_START  "1" para correr una vez al arrancar      (default 0)
    TZ            zona horaria (la maneja el SO/contenedor, p.ej. America/Argentina/Buenos_Aires)
"""

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta

DIA = int(os.getenv("DIA_SEMANA", "0"))      # 0 = lunes
HORA = int(os.getenv("HORA", "9"))
MINUTO = int(os.getenv("MINUTO", "0"))
RUN_ON_START = os.getenv("RUN_ON_START", "0") == "1"


def proxima_ejecucion(ahora: datetime) -> datetime:
    """Devuelve el próximo datetime que caiga en DIA a las HORA:MINUTO."""
    objetivo = ahora.replace(hour=HORA, minute=MINUTO, second=0, microsecond=0)
    dias = (DIA - ahora.weekday()) % 7
    objetivo += timedelta(days=dias)
    if objetivo <= ahora:
        objetivo += timedelta(days=7)
    return objetivo


def correr() -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] ▶ generando playlists…", flush=True)
    r = subprocess.run([sys.executable, "-u", "playlists.py"], cwd=os.path.dirname(__file__) or ".")
    estado = "OK" if r.returncode == 0 else f"ERROR (code {r.returncode})"
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] ■ terminado: {estado}", flush=True)


def main() -> int:
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    print(f"Scheduler activo — corre cada {dias[DIA]} a las {HORA:02d}:{MINUTO:02d}.", flush=True)

    if RUN_ON_START:
        correr()

    while True:
        prox = proxima_ejecucion(datetime.now())
        print(f"[{datetime.now():%Y-%m-%d %H:%M}] próxima corrida: {prox:%Y-%m-%d %H:%M} "
              f"(en {(prox - datetime.now()).total_seconds() / 3600:.1f} h)", flush=True)
        # dormir en tramos de <=1h para tolerar cambios de reloj / suspensión del host
        while datetime.now() < prox:
            time.sleep(min((prox - datetime.now()).total_seconds(), 3600))
        correr()


if __name__ == "__main__":
    sys.exit(main())
