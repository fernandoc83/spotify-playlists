#!/usr/bin/env python3
"""
Spotify Analyzer — analiza tu historial, tops y géneros.

Uso:
    python analyzer.py top-artists        # tus artistas más escuchados
    python analyzer.py top-tracks         # tus canciones más escuchadas
    python analyzer.py recent             # historial reciente (últimas 50)
    python analyzer.py recommend          # artistas afines (red de colaboraciones)
    python analyzer.py all                # todo lo anterior

Rango temporal (para top-artists / top-tracks / recommend):
    --range short|medium|long
        short  = últimas ~4 semanas
        medium = últimos ~6 meses   (por defecto)
        long   = de siempre / ~1 año
"""

import argparse
import sys
from collections import Counter

import pandas as pd
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth
from tabulate import tabulate

# Scopes para análisis + creación de playlists.
SCOPE = (
    "user-top-read user-read-recently-played "
    "user-library-read user-follow-read "
    "playlist-read-private playlist-modify-private playlist-modify-public"
)

RANGE_MAP = {
    "short": "short_term",
    "medium": "medium_term",
    "long": "long_term",
}


def get_client() -> spotipy.Spotify:
    """Crea el cliente autenticado. Abre el navegador la primera vez.

    En modo headless (var SPOTIPY_HEADLESS=1, p.ej. dentro de Docker) NO intenta
    abrir el navegador: se apoya en el token ya cacheado (.cache) que se refresca
    solo. Si el refresh token muriera, hay que re-autenticar una vez en local.
    """
    import os
    load_dotenv()
    headless = os.getenv("SPOTIPY_HEADLESS") == "1"
    auth = SpotifyOAuth(scope=SCOPE, open_browser=not headless)
    return spotipy.Spotify(auth_manager=auth)


def show(df: pd.DataFrame, title: str) -> None:
    print(f"\n=== {title} ===")
    if df.empty:
        print("(sin datos)")
        return
    print(tabulate(df, headers="keys", tablefmt="rounded_outline", showindex=False))


# --------------------------------------------------------------------------- #
# Comandos
# --------------------------------------------------------------------------- #
def top_artists(sp, time_range="medium_term", limit=20) -> pd.DataFrame:
    # Nota: Spotify ya no incluye 'genres'/'popularity' en esta respuesta (vienen null).
    items = sp.current_user_top_artists(limit=limit, time_range=time_range)["items"]
    rows = [
        {"#": i + 1, "Artista": a["name"]}
        for i, a in enumerate(items)
    ]
    return pd.DataFrame(rows)


def top_tracks(sp, time_range="medium_term", limit=20) -> pd.DataFrame:
    items = sp.current_user_top_tracks(limit=limit, time_range=time_range)["items"]
    rows = [
        {
            "#": i + 1,
            "Canción": t["name"],
            "Artista": ", ".join(a["name"] for a in t["artists"]),
            "Álbum": t["album"]["name"],
        }
        for i, t in enumerate(items)
    ]
    return pd.DataFrame(rows)


def recent(sp, limit=50) -> pd.DataFrame:
    items = sp.current_user_recently_played(limit=limit)["items"]
    rows = [
        {
            "Reproducido (UTC)": it["played_at"][:19].replace("T", " "),
            "Canción": it["track"]["name"],
            "Artista": ", ".join(a["name"] for a in it["track"]["artists"]),
        }
        for it in items
    ]
    return pd.DataFrame(rows)


def recommend(sp, time_range="medium_term", seed_n=15) -> pd.DataFrame:
    """
    Recomendador por red de colaboraciones.

    Spotify deprecó /recommendations y /related-artists, y ya no entrega géneros.
    Pero el endpoint de álbumes sí funciona: para cada uno de tus artistas top
    miramos sus apariciones (compilados/colaboraciones, 'appears_on') y juntamos
    a los demás artistas que comparten esos discos. Los que más se repiten — y que
    todavía no escuchás — son tu recomendación.
    """
    arts = sp.current_user_top_artists(limit=50, time_range=time_range)["items"]
    conocidos = {a["name"].lower() for a in arts}
    # "Various Artists" y variantes son ruido de los compilados, no recomendaciones.
    ruido = {"various artists", "varios artistas", "various", "v.a."}

    counter = Counter()          # artista candidato -> cuántas veces aparece
    via = {}                     # artista candidato -> a través de cuál de tus tops
    for a in arts[:seed_n]:
        try:
            albums = sp.artist_albums(
                a["id"], include_groups="appears_on", limit=10
            )["items"]
        except Exception:
            continue
        for al in albums:
            for ar in al["artists"]:
                nombre = ar["name"]
                low = nombre.lower()
                if low in conocidos or low in ruido or low == a["name"].lower():
                    continue
                counter[nombre] += 1
                via.setdefault(nombre, a["name"])

    rows = [
        {"#": i + 1, "Artista sugerido": nombre, "Afinidad": n, "Porque escuchás": via[nombre]}
        for i, (nombre, n) in enumerate(counter.most_common(25))
    ]
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description="Analiza tu Spotify.")
    parser.add_argument(
        "command",
        choices=["top-artists", "top-tracks", "recent", "recommend", "all"],
    )
    parser.add_argument("--range", choices=RANGE_MAP, default="medium")
    args = parser.parse_args()

    tr = RANGE_MAP[args.range]
    sp = get_client()
    me = sp.current_user()
    print(f"Conectado como: {me['display_name']} ({me['id']})")

    cmd = args.command
    if cmd in ("top-artists", "all"):
        show(top_artists(sp, tr), f"Top artistas ({args.range})")
    if cmd in ("top-tracks", "all"):
        show(top_tracks(sp, tr), f"Top canciones ({args.range})")
    if cmd in ("recent", "all"):
        show(recent(sp), "Reproducido recientemente")
    if cmd in ("recommend", "all"):
        show(recommend(sp, tr), "Artistas afines (red de colaboraciones)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
