import os
import time
from urllib import response
import uuid
import random
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from wsgiref import headers

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "http://localhost:8080").rstrip("/")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")
SEED_TAG = os.getenv("SEED_TAG", "[SEED]")

assert AUTH_TOKEN, "Definí AUTH_TOKEN en .env"

H = {"Authorization": f"Bearer {AUTH_TOKEN}", "Content-Type": "application/json"}

# ---------------------------
# Helpers HTTP
# ---------------------------
def jprint(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"status": resp.status_code, "text": resp.text[:2000]}

def post(path: str, json: Any = None, headers: Optional[Dict[str, str]] = None):
    r = requests.post(f"{BASE_URL}{path}", json=json, headers=headers or H, timeout=30)
    if not r.ok and r.status_code != 201 and r.status_code != 200:
        raise RuntimeError(f"POST {path} failed: {r.status_code} {r.text}")
    return r

def put(path: str, json: Any = None, headers: Optional[Dict[str, str]] = None):
    r = requests.put(f"{BASE_URL}{path}", json=json, headers=headers or H, timeout=30)
    if not r.ok:
        raise RuntimeError(f"PUT {path} failed: {r.status_code} {r.text}")
    return r

def get(path: str, headers: Optional[Dict[str, str]] = None):
    r = requests.get(f"{BASE_URL}{path}", headers=headers or H, timeout=30)
    if not r.ok:
        raise RuntimeError(f"GET {path} failed: {r.status_code} {r.text}")
    return r

def delete(path: str, headers: Optional[Dict[str, str]] = None, tolerate_404=True):
    r = requests.delete(f"{BASE_URL}{path}", headers=headers or H, timeout=30)
    if not r.ok and not (tolerate_404 and r.status_code == 404):
        raise RuntimeError(f"DELETE {path} failed: {r.status_code} {r.text}")
    return r

# ---------------------------
# Datos a seedear
# ---------------------------
artists = [
    "Luna Rivera", "Atlas Vega", "Nora Fields", "Kairo Sun",
    "Mila Duarte", "Echo Valen", "Río Navarro", "Zoe Marín",
    "Bruno Ciel", "Iris K."
]

# 20 canciones (title, artist, duration mm:ss)
songs_plan = [
    ("Midnight Echoes", "Luna Rivera", "03:21"),
    ("Neon Birds", "Atlas Vega", "02:58"),
    ("Paper Boats", "Nora Fields", "04:12"),
    ("Sahara Lines", "Kairo Sun", "03:47"),
    ("Quiet Maps", "Mila Duarte", "03:05"),
    ("Static Flowers", "Echo Valen", "02:42"),
    ("Delta Dreams", "Río Navarro", "03:33"),
    ("Velvet Skies", "Zoe Marín", "03:19"),
    ("Glass Horizon", "Bruno Ciel", "03:55"),
    ("Indigo Rooms", "Iris K.", "02:51"),
    ("Northern Lights", "Luna Rivera", "04:01"),
    ("Saturn Drive", "Atlas Vega", "03:26"),
    ("Winter Letters", "Nora Fields", "03:48"),
    ("Mirage Parade", "Kairo Sun", "03:14"),
    ("Sunset Recipes", "Mila Duarte", "02:59"),
    ("Fading Signals", "Echo Valen", "03:40"),
    ("Tidal Canvas", "Río Navarro", "04:08"),
    ("Comet Walls", "Bruno Ciel", "03:02"),
    ("Caffeine Blue", "Zoe Marín", "02:47"),
    ("Lullaby for Cities", "Iris K.", "03:36"),
]

playlists_plan = [
    "Daily Focus", "Warm Vibes", "Indie Morning", "Late Night Coding", "Fresh Finds",
    "Road Trip '25", "Deep Work", "LoFi Breeze", "Weekend Sprint", "Acoustic Corner"
]

# Collections: (name, type, artist)
collections_plan = [
    ("Night Fragments", "album", "Luna Rivera"),
    ("Desert Neon", "album", "Atlas Vega"),
    ("Paper Seasons", "ep", "Nora Fields"),
    ("Solar Drift", "ep", "Kairo Sun"),
    ("Signals", "single", "Echo Valen"),
    ("Blue Delta", "album", "Río Navarro"),
]

# ---------------------------
# Utilidades de idempotencia
# ---------------------------
def with_tag(name: str) -> str:
    return f"{SEED_TAG} {name}"

def fetch_all_songs_index_by_title() -> Dict[str, Dict]:
    response = get(f"/songs")
    response.raise_for_status()


    payload = response.json()
    songs = payload.get("data", [])
    by_title = {s.get("title"): s for s in songs}
    return by_title

def find_song_id_by_title(title: str, cache: Dict[str, Dict]) -> Optional[str]:
    item = cache.get(title)
    return item.get("_id") if item else None

# Simulamos un catálogo de artistas con IDs sintéticos (UUID). Tu API no expone artistas,
# pero /collections requiere artistId/artistName. Guardamos en memoria.
artist_id_map: Dict[str, str] = {a: str(uuid.uuid4()) for a in artists}

# ---------------------------
# Seeder
# ---------------------------
def seed_songs() -> Dict[str, str]:
    """
    Crea 20 canciones. Como POST /songs no acepta artist,
    luego hacemos PUT /songs/{id} para fijar 'artist'.
    Devuelve dict title->song_id.
    """
    print("→ Seeding songs...")
    cache = fetch_all_songs_index_by_title()
    title_to_id: Dict[str, str] = {}

    for title, artist, duration in songs_plan:
        t_title = with_tag(title)
        existing_id = find_song_id_by_title(t_title, cache)
        if existing_id:
            title_to_id[t_title] = existing_id
            continue

        # 1) Crear la canción (sin artist)
        body = {"title": t_title, "duration": duration}
        r = post("/songs/", json=body)
        created = jprint(r)

        # Intentamos leer id; si el schema de respuesta no lo trae,
        # refrescamos cache y buscamos por título.
        sid = (created.get("id") if isinstance(created, dict) else None)
        if not sid:
            time.sleep(0.3)
            cache = fetch_all_songs_index_by_title()
            sid = find_song_id_by_title(t_title, cache)
            if not sid:
                raise RuntimeError(f"No pude obtener id de la canción '{t_title}'")

        # 2) Setear el artista con PUT
        put(f"/songs/{sid}", json={"title": t_title, "artist": artist, "duration": duration})

        title_to_id[t_title] = sid
        time.sleep(0.05)

    print(f"  ✓ Canciones listas: {len(title_to_id)}")
    return title_to_id

def seed_playlists(song_ids: List[str]) -> List[str]:
    print("→ Seeding playlists...")
    created_ids: List[str] = []

    # Rotamos canciones para no repetir patrón siempre
    shuffled = song_ids[:]
    random.shuffle(shuffled)

    for i, name in enumerate(playlists_plan):
        pname = with_tag(name)
        # No hay endpoint para buscar por nombre: creamos sin chequear y si falla por duplicado
        # (si tu backend valida nombres únicos) se podría ignorar el error.
        body = {"name": pname, "description": f"{pname} autogenerated"}
        r = post("/playlists/", json=body)
        pl = jprint(r)
        pid = pl.get("id")
        if not pid:
            # Si no vuelve id, tratemos de obtener todas y match por nombre (si la API retorna name)
            payload = get("/playlists/").json() or {}
            all_pl = payload.get("data", [])
            match = next((p for p in all_pl if p.get("name") == pname), None)
            if not match:
                raise RuntimeError(f"No pude obtener id de playlist '{pname}'")
            pid = match.get("id")

        created_ids.append(pid)

        # asignamos de 5 a 8 canciones por playlist
        take = random.randint(5, 8)
        picks = shuffled[i:i+take] if i + take <= len(shuffled) else random.sample(song_ids, take)
        for sid in picks:
            post(f"/playlists/{pid}/songs/{sid}")

        # Publicamos la mitad; las no publicadas quedan privadas por defecto (no llamar /private)
        if i < len(playlists_plan)//2:
            post(f"/playlists/{pid}/publish")
        # else: no-op

        time.sleep(0.05)

    print(f"  ✓ Playlists listas: {len(created_ids)} (mitad publicadas)")
    return created_ids

def seed_collections(title_to_id: Dict[str, str]):
    print("→ Seeding collections (albums/eps/singles)...")
    # armamos tracklists sencillas por artista
    songs_by_artist: Dict[str, List[str]] = {}
    for full_title, sid in title_to_id.items():
        # full_title = "[SEED] Title"
        # Para mapear artista, necesitamos consultar el song data; si tu API /songs/ incluye artist, mejor.
        # Para evitar N requests, inferimos del plan:
        base = full_title.replace(f"{SEED_TAG} ", "")
        artist = next((a for (t, a, _) in songs_plan if t == base), None)
        if not artist:
            continue
        songs_by_artist.setdefault(artist, []).append(sid)

    for name, ctype, artist in collections_plan:
        tname = with_tag(name)
        song_ids = (songs_by_artist.get(artist) or [])[:6] or list(title_to_id.values())[:3]
        body = {
            "name": tname,
            "artistId": artist_id_map[artist],
            "artistName": artist,
            "type": ctype,  # album|single|ep
            "songIds": song_ids
        }
        post("/collections/", json=body)
        time.sleep(0.05)

    print("  ✓ Collections listas.")

def seed_liked_songs_and_history(any_song_ids: List[str]):
    print("→ Seeding liked songs & history para listener genérico...")
    # Creamos la playlist especial de liked songs para el usuario actual (AUTH_TOKEN).
    post("/likedSongs/")

    liked = random.sample(any_song_ids, k=min(5, len(any_song_ids)))
    for sid in liked:
        post(f"/likedSongs/{sid}")
        time.sleep(0.02)

    # Historial de escucha (10 eventos) y updates de progreso en algunos
    history_sample = random.sample(any_song_ids, k=min(10, len(any_song_ids)))
    for i, sid in enumerate(history_sample):
        post("/history/", json={"songId": sid, "progress": 0})
        # Simulamos que escuchó ~30% del track en algunos
        if i % 2 == 0:
            put("/history/", json={"songId": sid, "progress": random.randint(20, 40)})
        time.sleep(0.02)

    print(f"  ✓ Liked={len(liked)}, history={len(history_sample)}")

def main():
    print(f"== Melodia Seeder ==\nBASE_URL={BASE_URL}\nTAG={SEED_TAG}\n")
    title_to_id = seed_songs()
    all_song_ids = list(title_to_id.values())

    seed_collections(title_to_id)
    seed_playlists(all_song_ids)
    seed_liked_songs_and_history(all_song_ids)

    print("\n✔️ Listo. Podés verificar con:")
    print("  - GET /songs/")
    print("  - GET /playlists/")
    print("  - GET /collections/")
    print("  - GET /history/")
    print("  - GET /likedSongs/")

if __name__ == "__main__":
    main()