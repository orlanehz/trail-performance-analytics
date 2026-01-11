import os, json, time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
import psycopg

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"

def must_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v

def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> Dict[str, Any]:
    r = requests.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Token refresh failed: {r.status_code} {r.text}")
    return r.json()

def strava_get(url: str, access_token: str, params: Optional[dict] = None) -> Any:
    r = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, params=params, timeout=60)
    if r.status_code == 429:
        raise RuntimeError("Rate limited by Strava (HTTP 429).")
    if r.status_code >= 400:
        raise RuntimeError(f"Strava API error: {r.status_code} {r.text}")
    return r.json()

def list_activities_since(access_token: str, after_epoch: int, per_page: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    page = 1
    while True:
        data = strava_get(
            f"{STRAVA_API_BASE}/athlete/activities",
            access_token,
            params={"after": after_epoch, "page": page, "per_page": per_page},
        )
        if not data:
            break
        out.extend(data)
        page += 1
        time.sleep(0.2)
    return out

def iso_to_epoch(s: str) -> int:
    # "2024-01-02T03:04:05Z"
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())

def main():
    load_dotenv()

    db_url = must_env("DATABASE_URL")
    client_id = must_env("STRAVA_CLIENT_ID")
    client_secret = must_env("STRAVA_CLIENT_SECRET")
    refresh_token = must_env("STRAVA_REFRESH_TOKEN")
    per_page = int(os.getenv("STRAVA_PER_PAGE", "50"))
    after_default = int(os.getenv("STRAVA_AFTER_EPOCH_DEFAULT", "0"))

    token_data = refresh_access_token(client_id, client_secret, refresh_token)
    access_token = token_data["access_token"]
    expires_at = int(token_data.get("expires_at") or 0)
    new_refresh = token_data.get("refresh_token") or refresh_token
    scope = token_data.get("scope")

    athlete = strava_get(f"{STRAVA_API_BASE}/athlete", access_token)
    athlete_id = int(athlete["id"])

    with psycopg.connect(db_url) as conn:
        conn.execute("set timezone to 'UTC';")

        # upsert athlete
        conn.execute(
            """
            insert into athletes (athlete_id, firstname, lastname, city, country, updated_at, raw)
            values (%s, %s, %s, %s, %s, now(), %s::jsonb)
            on conflict (athlete_id) do update set
              firstname=excluded.firstname,
              lastname=excluded.lastname,
              city=excluded.city,
              country=excluded.country,
              updated_at=now(),
              raw=excluded.raw
            """,
            (athlete_id, athlete.get("firstname"), athlete.get("lastname"), athlete.get("city"), athlete.get("country"), json.dumps(athlete)),
        )

        # upsert tokens
        conn.execute(
            """
            insert into strava_tokens (athlete_id, access_token, refresh_token, expires_at, scope, updated_at)
            values (%s, %s, %s, %s, %s, now())
            on conflict (athlete_id) do update set
              access_token=excluded.access_token,
              refresh_token=excluded.refresh_token,
              expires_at=excluded.expires_at,
              scope=excluded.scope,
              updated_at=now()
            """,
            (athlete_id, access_token, new_refresh, expires_at, scope),
        )

        # read state
        row = conn.execute(
            "select value from ingestion_state where athlete_id=%s and source='strava' and key='last_after_epoch'",
            (athlete_id,),
        ).fetchone()
        after_epoch = int(row[0]) if row else after_default

        print(f"🔄 Sync athlete={athlete_id} after_epoch={after_epoch}")
        activities = list_activities_since(access_token, after_epoch, per_page)
        print(f"📥 Retrieved {len(activities)} activities")

        max_epoch = after_epoch
        for a in activities:
            start_date = a.get("start_date")
            start_latlng = a.get("start_latlng") or [None, None]
            start_lat, start_lng = (start_latlng + [None, None])[:2]

            conn.execute(
                """
                insert into activities (
                  activity_id, athlete_id, name, sport_type, start_date, timezone,
                  elapsed_time, moving_time, distance_m, total_elevation_gain_m,
                  average_speed_mps, max_speed_mps, average_heartrate, max_heartrate,
                  average_watts, max_watts, average_cadence,
                  visibility, trainer, commute, start_lat, start_lng,
                  updated_at, raw
                )
                values (
                  %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s,
                  %s, %s, %s, %s,
                  %s, %s, %s,
                  %s, %s, %s, %s, %s,
                  now(), %s::jsonb
                )
                on conflict (activity_id) do update set
                  athlete_id=excluded.athlete_id,
                  name=excluded.name,
                  sport_type=excluded.sport_type,
                  start_date=excluded.start_date,
                  timezone=excluded.timezone,
                  elapsed_time=excluded.elapsed_time,
                  moving_time=excluded.moving_time,
                  distance_m=excluded.distance_m,
                  total_elevation_gain_m=excluded.total_elevation_gain_m,
                  average_speed_mps=excluded.average_speed_mps,
                  max_speed_mps=excluded.max_speed_mps,
                  average_heartrate=excluded.average_heartrate,
                  max_heartrate=excluded.max_heartrate,
                  average_watts=excluded.average_watts,
                  max_watts=excluded.max_watts,
                  average_cadence=excluded.average_cadence,
                  visibility=excluded.visibility,
                  trainer=excluded.trainer,
                  commute=excluded.commute,
                  start_lat=excluded.start_lat,
                  start_lng=excluded.start_lng,
                  updated_at=now(),
                  raw=excluded.raw
                """,
                (
                    int(a["id"]), athlete_id,
                    a.get("name"), a.get("sport_type") or a.get("type"),
                    start_date, a.get("timezone"),
                    a.get("elapsed_time"), a.get("moving_time"),
                    a.get("distance"), a.get("total_elevation_gain"),
                    a.get("average_speed"), a.get("max_speed"),
                    a.get("average_heartrate"), a.get("max_heartrate"),
                    a.get("average_watts"), a.get("max_watts"),
                    a.get("average_cadence"),
                    a.get("visibility"), a.get("trainer"), a.get("commute"),
                    start_lat, start_lng,
                    json.dumps(a),
                ),
            )

            if start_date:
                max_epoch = max(max_epoch, iso_to_epoch(start_date))

        # advance state with margin
        if max_epoch > after_epoch:
            conn.execute(
                """
                insert into ingestion_state (athlete_id, source, key, value, updated_at)
                values (%s, 'strava', 'last_after_epoch', %s, now())
                on conflict (athlete_id, source, key) do update set
                  value=excluded.value, updated_at=now()
                """,
                (athlete_id, str(max_epoch - 60)),
            )

        conn.commit()

    print("✅ Done")

if __name__ == "__main__":
    main()
