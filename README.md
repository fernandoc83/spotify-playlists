# Spotify Analyzer

Analiza tu historial, tus tops y descubre artistas afines, desde la terminal.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env   # y completá tus credenciales
```

Las credenciales se sacan del [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
Redirect URI (exacto): `http://127.0.0.1:8888/callback`

## Uso

```bash
.venv/bin/python analyzer.py top-artists --range short   # últimas ~4 semanas
.venv/bin/python analyzer.py top-tracks  --range long    # de siempre
.venv/bin/python analyzer.py recent                      # últimas 50 escuchadas
.venv/bin/python analyzer.py recommend                   # artistas afines
.venv/bin/python analyzer.py all
```

Rango: `--range short | medium | long` (por defecto `medium`).

## Playlists con variedad

```bash
.venv/bin/python playlists.py             # regenera las 3
.venv/bin/python playlists.py biblioteca  # solo una (biblioteca | seguidos | escuchando)
.venv/bin/python playlists.py --dry-run   # muestra qué armaría, sin tocar Spotify
```

Cada corrida **reutiliza las mismas 3 playlists**: les borra el contenido viejo y
mete música nueva barajada desde tu propia huella. No usa el algoritmo de Spotify.
Cada una sale de una fuente distinta:

| Lista | `key` | Fuente |
|---|---|---|
| 🎲 Biblioteca a fondo | `biblioteca` | Tus Me gusta + tus propias playlists |
| 🔭 Bandas que sigo | `seguidos` | Artistas que seguís (todos, sin importar cuánto los escuchás) |
| 🎧 En rotación | `escuchando` | Lo que venís escuchando último (historial reciente + tus tops) |

## Automatización semanal (Docker)

Pensado para un homeserver siempre encendido. Regenera las playlists 1×/semana
sin depender de tu PC. El token OAuth queda dentro del contenedor y se refresca solo.

**Requisito:** tener `.env` y `.cache` (token ya autenticado una vez en local) en
esta carpeta. `.cache` debe existir como archivo antes de levantar (el volumen lo mapea).

```bash
# en el homeserver, dentro de la carpeta del proyecto:
docker compose up -d --build      # buildea y levanta en segundo plano
docker compose logs -f            # ver actividad / próxima corrida
docker compose down               # detener
```

**La config va en tu `.env`** (no en `docker-compose.yml`), así podés cambiarla
sin conflictos al hacer `git pull`. Variables (todas opcionales, ver `.env.example`):

| Var | Qué controla | Default |
|---|---|---|
| `FRECUENCIA` | `diario` \| `semanal` \| `mensual` | `semanal` |
| `HORA` / `MINUTO` | hora local de la corrida | `9:00` |
| `DIA_SEMANA` | solo si `semanal`: 0=lunes … 6=domingo | `0` (lunes) |
| `DIA_MES` | solo si `mensual`: 1-31 (se ajusta si el mes es más corto) | `1` |
| `RUN_ON_START` | `1` = corre al levantar (útil para probar) | `0` |
| `TZ` | zona horaria | `America/Argentina/Buenos_Aires` |

Ejemplos en `.env`: `FRECUENCIA=diario` + `HORA=8` (todos los días 08:00) ·
`FRECUENCIA=mensual` + `DIA_MES=1` (el día 1 de cada mes) ·
`FRECUENCIA=semanal` + `DIA_SEMANA=5` (todos los sábados).

Tras editar el `.env`: `docker compose up -d` (recrea el contenedor con los valores nuevos).

> Si el refresh token de Spotify se venciera (raro, solo si lo revocás), hay que
> re-autenticar una vez en local (`python playlists.py`) y volver a copiar `.cache`.

## Notas sobre la API (2024+)

Spotify recortó varios datos/endpoints para apps en development mode:

- `genres` y `popularity` ahora vienen **null** → no se muestran.
- `/recommendations`, `/related-artists` y `/artists/{id}/top-tracks` → **403/404**.

Por eso el recomendador es **casero**: usa el endpoint de álbumes (`appears_on`)
para encontrar artistas que comparten compilados/colaboraciones con tus favoritos.
Si en el futuro querés géneros, se pueden traer de Last.fm o MusicBrainz.
