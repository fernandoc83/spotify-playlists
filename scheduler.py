#!/usr/bin/env python3
"""
Scheduler para regenerar las playlists dentro de Docker.

Duerme hasta el próximo horario configurado, corre `playlists.py`, y repite.
No usa cron ni dependencias extra: solo stdlib.

Config por variables de entorno (todas opcionales):
    FRECUENCIA    "diario" | "semanal" | "mensual"         (default "semanal")
    HORA          hora del día 0-23                        (default 9)
    MINUTO        minuto 0-59                              (default 0)
    DIA_SEMANA    solo si FRECUENCIA=semanal: 0=lunes … 6=domingo   (default 0 = lunes)
    DIA_MES       solo si FRECUENCIA=mensual: día 1-31 (se ajusta si el mes es más corto) (default 1)
    RUN_ON_START  "1" para correr una vez al arrancar      (default 0)
    TZ            zona horaria (la maneja el SO/contenedor, p.ej. America/Argentina/Buenos_Aires)
"""

import calendar
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta

FRECUENCIA = os.getenv("FRECUENCIA", "semanal").strip().lower()
HORA = int(os.getenv("HORA", "9"))
MINUTO = int(os.getenv("MINUTO", "0"))
DIA_SEMANA = int(os.getenv("DIA_SEMANA", "0"))   # 0 = lunes
DIA_MES = int(os.getenv("DIA_MES", "1"))         # 1-31
RUN_ON_START = os.getenv("RUN_ON_START", "0") == "1"

if FRECUENCIA not in ("diario", "semanal", "mensual"):
    print(f"FRECUENCIA inválida: {FRECUENCIA!r}. Usá diario|semanal|mensual.", file=sys.stderr)
    sys.exit(2)


def _a_hora(dt: datetime) -> datetime:
    return dt.replace(hour=HORA, minute=MINUTO, second=0, microsecond=0)


def _mes_dia(anio: int, mes: int, dia: int) -> datetime:
    """datetime en (anio, mes) al día pedido, recortado al último día si el mes es más corto."""
    ultimo = calendar.monthrange(anio, mes)[1]
    return datetime(anio, mes, min(dia, ultimo), HORA, MINUTO)


def proxima_ejecucion(ahora: datetime) -> datetime:
    """Próximo datetime de ejecución según FRECUENCIA."""
    if FRECUENCIA == "diario":
        objetivo = _a_hora(ahora)
        if objetivo <= ahora:
            objetivo += timedelta(days=1)
        return objetivo

    if FRECUENCIA == "mensual":
        objetivo = _mes_dia(ahora.year, ahora.month, DIA_MES)
        if objetivo <= ahora:
            mes = ahora.month + 1
            anio = ahora.year + (mes > 12)
            mes = mes - 12 if mes > 12 else mes
            objetivo = _mes_dia(anio, mes, DIA_MES)
        return objetivo

    # semanal
    objetivo = _a_hora(ahora) + timedelta(days=(DIA_SEMANA - ahora.weekday()) % 7)
    if objetivo <= ahora:
        objetivo += timedelta(days=7)
    return objetivo


def correr() -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] ▶ generando playlists…", flush=True)
    r = subprocess.run([sys.executable, "-u", "playlists.py"], cwd=os.path.dirname(__file__) or ".")
    estado = "OK" if r.returncode == 0 else f"ERROR (code {r.returncode})"
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] ■ terminado: {estado}", flush=True)


def _descripcion() -> str:
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    hhmm = f"{HORA:02d}:{MINUTO:02d}"
    if FRECUENCIA == "diario":
        return f"todos los días a las {hhmm}"
    if FRECUENCIA == "mensual":
        return f"el día {DIA_MES} de cada mes a las {hhmm}"
    return f"cada {dias[DIA_SEMANA]} a las {hhmm}"


def main() -> int:
    print(f"Scheduler activo — corre {_descripcion()}.", flush=True)

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
