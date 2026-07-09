#!/usr/bin/env python3
"""
Constructor de playlists con variedad forzada.

No usa el algoritmo de Spotify: arma las listas desde TU propia huella
(temas guardados, tus playlists, artistas que seguís) y reparte la variedad
a mano (tope por artista + barajado), para romper el loop de "siempre lo mismo".

Uso:
    python playlists.py                      # arma las 3 (biblioteca, seguidos, joyas)
    python playlists.py biblioteca           # solo una
    python playlists.py --dry-run            # muestra qué armaría, sin crear nada
"""

import argparse
import random
import sys
import time
from collections import defaultdict

from analyzer import get_client

# ---- parámetros ajustables ----------------------------------------------- #
TAMANO = 50            # temas por playlist
MAX_POR_ARTISTA = 1    # variedad: cuántos temas como mucho por artista
SEGUIDOS_MAX = 50      # cuántos artistas seguidos procesar (1 búsqueda c/u)
SEGUIDOS_POR_ART = 2   # temas a tomar de cada seguido


# --------------------------------------------------------------------------- #
# Recolección de datos
# --------------------------------------------------------------------------- #
def _track_min(t):
    """Normaliza un track a lo que nos importa, o None si no sirve."""
    if not t or not t.get("id") or t.get("is_local"):
        return None
    return {
        "id": t["id"],
        "uri": t["uri"],
        "name": t["name"],
        "artist": t["artists"][0]["name"] if t["artists"] else "?",
        "artist_id": t["artists"][0]["id"] if t["artists"] else None,
    }


def saved_tracks(sp, max_n=2000):
    out, off = [], 0
    while off < max_n:
        page = sp.current_user_saved_tracks(limit=50, offset=off)
        items = page["items"]
        if not items:
            break
        for it in items:
            tm = _track_min(it.get("track"))
            if tm:
                out.append(tm)
        off += 50
        if len(items) < 50:
            break
    return out


def my_playlist_tracks(sp, max_per=200):
    me = sp.current_user()["id"]
    out, off = [], 0
    pls = []
    while True:
        page = sp.current_user_playlists(limit=50, offset=off)
        pls += page["items"]
        if len(page["items"]) < 50:
            break
        off += 50
    for pl in pls:
        # solo las tuyas (no las que seguís de otros)
        if pl["owner"]["id"] != me:
            continue
        o = 0
        while o < max_per:
            page = sp.playlist_items(
                pl["id"], limit=100, offset=o,
                fields="items.track.id,items.track.uri,items.track.name,"
                       "items.track.is_local,items.track.artists",
            )
            items = page["items"]
            if not items:
                break
            for it in items:
                tm = _track_min(it.get("track"))
                if tm:
                    out.append(tm)
            o += 100
            if len(items) < 100:
                break
    return out


def followed_artists(sp):
    out, after = [], None
    while True:
        page = sp.current_user_followed_artists(limit=50, after=after)["artists"]
        out += page["items"]
        after = page.get("cursors", {}).get("after")
        if not after:
            break
    return out


def recent_rotation_ids(sp):
    """IDs de lo que ya está sonando seguido (historial + tops recientes)."""
    ids = set()
    for it in sp.current_user_recently_played(limit=50)["items"]:
        tm = _track_min(it.get("track"))
        if tm:
            ids.add(tm["id"])
    for tr in ("short_term", "medium_term"):
        for t in sp.current_user_top_tracks(limit=50, time_range=tr)["items"]:
            if t.get("id"):
                ids.add(t["id"])
    return ids


def artist_some_tracks(sp, artist_id, artist_name, n=2):
    """Devuelve hasta n temas de un artista vía búsqueda (1 sola llamada, liviano)."""
    try:
        res = sp.search(q=f'artist:"{artist_name}"', type="track", limit=10)
    except Exception:
        return []
    cands = []
    for t in res["tracks"]["items"]:
        tm = _track_min(t)
        if tm and any(a["id"] == artist_id for a in t["artists"]):
            cands.append(tm)
    random.shuffle(cands)
    return cands[:n]


# --------------------------------------------------------------------------- #
# Variedad
# --------------------------------------------------------------------------- #
def diversificar(tracks, size, max_por_artista):
    """Baraja y limita cuántos temas entran por artista; quita duplicados."""
    random.shuffle(tracks)
    vistos, por_art, out = set(), defaultdict(int), []
    for t in tracks:
        if t["id"] in vistos:
            continue
        if por_art[t["artist"].lower()] >= max_por_artista:
            continue
        vistos.add(t["id"])
        por_art[t["artist"].lower()] += 1
        out.append(t)
        if len(out) >= size:
            break
    return out


# --------------------------------------------------------------------------- #
# Constructores de cada playlist
# --------------------------------------------------------------------------- #
def build_biblioteca(sp):
    print("  → leyendo temas guardados…")
    pool = saved_tracks(sp)
    print(f"    {len(pool)} guardados")
    print("  → leyendo tus playlists…")
    pl = my_playlist_tracks(sp)
    print(f"    {len(pl)} de playlists")
    sel = diversificar(pool + pl, TAMANO, MAX_POR_ARTISTA)
    return ("🎲 Biblioteca a fondo",
            "Todo lo tuyo, máximo 1 tema por artista y barajado. Generada con Claude.",
            sel)


def build_joyas(sp):
    print("  → calculando tu rotación reciente…")
    recientes = recent_rotation_ids(sp)
    print(f"    {len(recientes)} temas en rotación (se excluyen)")
    print("  → leyendo guardados + playlists…")
    pool = saved_tracks(sp) + my_playlist_tracks(sp)
    olvidados = [t for t in pool if t["id"] not in recientes]
    print(f"    {len(olvidados)} candidatos olvidados")
    sel = diversificar(olvidados, TAMANO, max(2, MAX_POR_ARTISTA))
    return ("💎 Joyas perdidas",
            "Temas tuyos que no aparecen en tu historial reciente. Generada con Claude.",
            sel)


def build_seguidos(sp):
    print("  → leyendo artistas que seguís…")
    foll = followed_artists(sp)
    print(f"    seguís {len(foll)} artistas")
    # priorizar los que NO están entre tus tops (los menos escuchados)
    top_ids = {a["id"] for tr in ("short_term", "medium_term", "long_term")
               for a in sp.current_user_top_artists(limit=50, time_range=tr)["items"]}
    candidatos = [a for a in foll if a["id"] not in top_ids] or foll
    random.shuffle(candidatos)
    candidatos = candidatos[:SEGUIDOS_MAX]
    print(f"  → buscando temas de {len(candidatos)} seguidos poco escuchados…")
    tracks = []
    for i, a in enumerate(candidatos, 1):
        tracks += artist_some_tracks(sp, a["id"], a["name"], SEGUIDOS_POR_ART)
        time.sleep(0.25)  # repartir las llamadas para no chocar el rate-limit
        if i % 15 == 0:
            print(f"    {i}/{len(candidatos)}…")
    sel = diversificar(tracks, TAMANO, SEGUIDOS_POR_ART)
    return ("🔭 Seguidos al rescate",
            "Artistas que seguís pero el algoritmo te esconde. Generada con Claude.",
            sel)


BUILDERS = {
    "biblioteca": build_biblioteca,
    "seguidos": build_seguidos,
    "joyas": build_joyas,
}


# --------------------------------------------------------------------------- #
# Crear en Spotify
# --------------------------------------------------------------------------- #
def _mis_playlists(sp):
    """Todas las playlists que sos dueño (paginado)."""
    me = sp.current_user()["id"]
    out, off = [], 0
    while True:
        page = sp.current_user_playlists(limit=50, offset=off)
        for pl in page["items"]:
            if pl and pl["owner"]["id"] == me:
                out.append(pl)
        if len(page["items"]) < 50:
            break
        off += 50
    return out


def crear_o_actualizar(sp, nombre, desc, tracks):
    """Si ya existe una playlist tuya con ese nombre, le reemplaza el contenido
    (misma URL, se borra lo viejo). Si no, la crea. Duplicados viejos se borran."""
    uris = [t["uri"] for t in tracks]
    existentes = [pl for pl in _mis_playlists(sp) if pl["name"] == nombre]

    if existentes:
        pid = existentes[0]["id"]
        # borrar duplicados si quedaron de corridas anteriores
        for extra in existentes[1:]:
            try:
                sp.current_user_unfollow_playlist(extra["id"])
            except Exception:
                pass
        # refrescar título/descripción por si cambió el texto
        try:
            sp.playlist_change_details(pid, name=nombre, description=desc)
        except Exception:
            pass
        # reemplazar (el 1er replace vacía y pone hasta 100; luego se agrega el resto)
        sp.playlist_replace_items(pid, uris[:100])
        for i in range(100, len(uris), 100):
            sp.playlist_add_items(pid, uris[i:i + 100])
        url = existentes[0]["external_urls"]["spotify"]
        return url, "actualizada"

    # Spotify dejó 403 el endpoint clásico /users/{id}/playlists; usar POST /me/playlists.
    pl = sp._post("me/playlists", payload={
        "name": nombre, "public": False, "description": desc,
    })
    for i in range(0, len(uris), 100):
        sp.playlist_add_items(pl["id"], uris[i:i + 100])
    return pl["external_urls"]["spotify"], "creada"


def main() -> int:
    parser = argparse.ArgumentParser(description="Arma playlists con variedad.")
    parser.add_argument("which", nargs="*", choices=list(BUILDERS) + [],
                        help="cuáles armar (por defecto: todas)")
    parser.add_argument("--dry-run", action="store_true",
                        help="muestra la selección sin crear nada en Spotify")
    args = parser.parse_args()

    which = args.which or list(BUILDERS)
    sp = get_client()
    me = sp.current_user()
    print(f"Conectado como: {me['display_name']} ({me['id']})\n")

    for key in which:
        print(f"== {key} ==")
        nombre, desc, sel = BUILDERS[key](sp)
        print(f"  Seleccionados {len(sel)} temas:")
        for t in sel[:8]:
            print(f"    • {t['name']} — {t['artist']}")
        if len(sel) > 8:
            print(f"    … (+{len(sel) - 8} más)")
        if not sel:
            print("  (vacío, se omite)\n")
            continue
        if args.dry_run:
            print("  [dry-run] no se creó nada.\n")
        else:
            url, accion = crear_o_actualizar(sp, nombre, desc, sel)
            print(f"  ✅ {accion}: {url}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
