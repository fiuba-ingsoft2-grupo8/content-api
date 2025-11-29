import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "http://localhost:8080").rstrip("/")
AUTH_ARTIST_TOKEN = os.getenv("AUTH_ARTIST_TOKEN", "")
SEED_TAG = os.getenv("SEED_TAG", "[SEED-2025-10]")

assert AUTH_ARTIST_TOKEN, "Definí AUTH_ARTIST_TOKEN en .env"

H = {
    "Authorization": f"Bearer {AUTH_ARTIST_TOKEN}",
    "Content-Type": "application/json",
}

def j(r):
    try: return r.json()
    except: return r.text

def delete_seed_collections():
    print(f"Buscando colecciones con TAG: {SEED_TAG}")

    r = requests.get(f"{BASE_URL}/collections", headers=H)
    if not r.ok:
        print("Error al obtener colecciones:", r.status_code, r.text)
        return

    payload = j(r)
    data = payload.get("data") or payload.get("items") or []

    count = 0
    for col in data:
        name = col.get("name", "")
        cid = col.get("_id") or col.get("id")

        if cid and name.startswith(SEED_TAG):
            print(f"  → Eliminando {name} ({cid})")
            dr = requests.delete(f"{BASE_URL}/collections/{cid}", headers=H)
            if dr.ok:
                count += 1
            else:
                print("    ⚠ Error:", dr.status_code, dr.text)

    print(f"\n✓ Eliminadas {count} colecciones con TAG {SEED_TAG}")

if __name__ == "__main__":
    delete_seed_collections()