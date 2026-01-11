import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

from db import get_conn, get_state, set_state

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"


def must_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> Dict[str, Any]:
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    r = requests.post(STRAVA_TOKEN_URL, data=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def strava_get(url: str, access_token: str, params: Optional[dict] = None) -> Any:
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, headers=headers, params=params, timeout=60)
    # gestion simple de rate-limit / erreurs
    if r.status_code == 429:
        # Strava renvoie souvent des headers de rate limit; on fait simple
        raise RuntimeError("Rate limited by Strava (HTTP 429). Try later or reduce frequency.")
    r.raise_for_status()
    return r.json()


def upsert_activity(conn, activity: Dict[str, Any]) -> None:
    activity_id = int(activity["id"])
    start_date = activity.get("start_date")  # ISO string
    updated_at = datetime.now(timezone.utc).isoformat()

    conn.execute(
        "INSERT INTO activities(id, json, start_date, updated_at) VALUES(?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET json=excluded.json, start_date=excluded.start_date, updated_at=excluded.updated_at",
        (activity_id, json.dumps(activity), start_date, updated_at),
    )


def list_activities_since(access_token: str, after_epoch: int, per_page: int = 50) -> List[Dict[str, Any]]:
    all_acts: List[Dict[str, Any]] = []
    page = 1

    while True:
        params = {
            "after": after_epoch,
            "page": page,
            "per_page": per_page,
        }
        data = strava_get(f"{STRAVA_API_BASE}/athlete/activities", access_token, params=params)
        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected response (expected list), got: {type(data)}")

        if len(data) == 0:
            break

        all_acts.extend(data)
        page += 1

        # petite pause pour être gentil avec l'API
        time.sleep(0.2)

    return all_acts


def main() -> None:
    load_dotenv()

    client_id = must_env("STRAVA_CLIENT_ID")
    client_secret = must_env("STRAVA_CLIENT_SECRET")
    refresh_token = must_env("STRAVA_REFRESH_TOKEN")
    per_page = int(os.getenv("STRAVA_PER_PAGE", "50"))

    conn = get_conn("strava.db")

    # curseur d'incrémental: last_after_epoch
    # par défaut: 0 => récupère "tout" (attention si compte très ancien)
    last_after = get_state(conn, "last_after_epoch")
    after_epoch = int(last_after) if last_after else 0

    token_data = refresh_access_token(client_id, client_secret, refresh_token)
    access_token = token_data["access_token"]

    # Optionnel: si Strava renvoie un nouveau refresh_token, tu peux le stocker (ex: dans Vercel ensuite)
    new_refresh = token_data.get("refresh_token")
    if new_refresh and new_refresh != refresh_token:
        print("⚠️ Strava returned a new refresh_token. Pense à le mettre à jour dans Vercel/.env")
        # tu peux aussi l'écrire dans state si tu veux:
        set_state(conn, "latest_refresh_token", new_refresh)

    print(f"🔄 Sync Strava activities after epoch={after_epoch} (per_page={per_page})")

    activities = list_activities_since(access_token, after_epoch=after_epoch, per_page=per_page)
    print(f"📥 Retrieved {len(activities)} activities")

    # upsert + calcul du nouveau curseur (max start_date)
    max_start_epoch = after_epoch

    for a in activities:
        upsert_activity(conn, a)

        # start_date est ISO UTC type "2024-01-02T03:04:05Z"
        sd = a.get("start_date")
        if sd:
            dt = datetime.fromisoformat(sd.replace("Z", "+00:00"))
            max_start_epoch = max(max_start_epoch, int(dt.timestamp()))

    conn.commit()

    # On avance le curseur (petite marge: -60s pour éviter de rater une activité à cheval)
    if max_start_epoch > after_epoch:
        set_state(conn, "last_after_epoch", str(max_start_epoch - 60))

    print("✅ Done. Data stored in strava.db")


if __name__ == "__main__":
    main()
