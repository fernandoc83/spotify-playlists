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
.venv/bin/python playlists.py            # regenera las 3 (biblioteca, seguidos, joyas)
.venv/bin/python playlists.py biblioteca # solo una
.venv/bin/python playlists.py --dry-run  # muestra qué armaría, sin tocar Spotify
```

Cada corrida **reutiliza las mismas 3 playlists** (URLs fijas): les borra el
contenido viejo y mete música nueva barajada desde tu propia huella (guardados,
tus playlists, artistas que seguís). No usa el algoritmo de Spotify.

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

Ajustes en `docker-compose.yml` (env vars):

| Var | Qué controla | Default |
|---|---|---|
| `DIA_SEMANA` | 0=lunes … 6=domingo | `0` (lunes) |
| `HORA` / `MINUTO` | hora local de la corrida | `9:00` |
| `RUN_ON_START` | `1` = corre al levantar (útil para probar) | `0` |
| `TZ` | zona horaria | `America/Argentina/Buenos_Aires` |

> Si el refresh token de Spotify se venciera (raro, solo si lo revocás), hay que
> re-autenticar una vez en local (`python playlists.py`) y volver a copiar `.cache`.

## Notas sobre la API (2024+)

Spotify recortó varios datos/endpoints para apps en development mode:

- `genres` y `popularity` ahora vienen **null** → no se muestran.
- `/recommendations`, `/related-artists` y `/artists/{id}/top-tracks` → **403/404**.

Por eso el recomendador es **casero**: usa el endpoint de álbumes (`appears_on`)
para encontrar artistas que comparten compilados/colaboraciones con tus favoritos.
Si en el futuro querés géneros, se pueden traer de Last.fm o MusicBrainz.
