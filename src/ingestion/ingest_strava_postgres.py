"""Strava → PostgreSQL ingestion (Supabase-ready).

What this script does
- Refreshes Strava access tokens using stored refresh tokens.
- Upserts athlete profile + tokens.
- Incrementally ingests athlete activities into `activities`.
- Tracks per-athlete incremental state in `ingestion_state`.

How to run
- Single athlete (env refresh token):
  python -m src.ingestion.ingest_strava_postgres

- Single athlete from DB (requires --athlete-id):
  python -m src.ingestion.ingest_strava_postgres --athlete-id 123

- Multi-athlete (all athletes that have a refresh token in DB):
  python -m src.ingestion.ingest_strava_postgres --all

Notes
- This script is designed for production-like usage (Supabase + GitHub Actions).
- For Strava rate-limits, it retries a few times with backoff.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import psycopg
import requests
from dotenv import load_dotenv

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"

LOG = logging.getLogger("ingest_strava")


def must_env(name: str) -> str:
    """Return required env var or raise a clear error."""
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def iso_to_epoch(s: str) -> int:
    # "2024-01-02T03:04:05Z"
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


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


def strava_get(url: str, access_token: str, params: Optional[dict] = None, *, max_retries: int = 4) -> Any:
    """GET helper with basic retry/backoff for Strava API errors and rate limits."""
    headers = {"Authorization": f"Bearer {access_token}"}

    for attempt in range(max_retries):
        r = requests.get(url, headers=headers, params=params, timeout=60)

        # Rate limit
        if r.status_code == 429:
            sleep_s = 2 ** attempt
            LOG.warning("Rate limited by Strava (429). Sleeping %ss then retrying...", sleep_s)
            time.sleep(sleep_s)
            continue

        # Transient errors
        if r.status_code in (500, 502, 503, 504):
            sleep_s = 2 ** attempt
            LOG.warning("Transient Strava error %s. Sleeping %ss then retrying...", r.status_code, sleep_s)
            time.sleep(sleep_s)
            continue

        if r.status_code >= 400:
            raise RuntimeError(f"Strava API error: {r.status_code} {r.text}")

        return r.json()

    raise RuntimeError("Strava API failed after retries")


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
        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected response (expected list), got: {type(data)}")
        out.extend(data)
        page += 1
        time.sleep(0.2)
    return out


def db_get_last_after_epoch(conn: psycopg.Connection, athlete_id: int, after_default: int) -> int:
    row = conn.execute(
        "select value from ingestion_state where athlete_id=%s and source='strava' and key='last_after_epoch'",
        (athlete_id,),
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else after_default


def db_set_last_after_epoch(conn: psycopg.Connection, athlete_id: int, value: int) -> None:
    conn.execute(
        """
        insert into ingestion_state (athlete_id, source, key, value, updated_at)
        values (%s, 'strava', 'last_after_epoch', %s, now())
        on conflict (athlete_id, source, key) do update set
          value=excluded.value, updated_at=now()
        """,
        (athlete_id, str(value)),
    )


def db_upsert_athlete(conn: psycopg.Connection, athlete: Dict[str, Any]) -> int:
    athlete_id = int(athlete["id"])
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
        (
            athlete_id,
            athlete.get("firstname"),
            athlete.get("lastname"),
            athlete.get("city"),
            athlete.get("country"),
            json.dumps(athlete),
        ),
    )
    return athlete_id


def db_upsert_tokens(
    conn: psycopg.Connection,
    athlete_id: int,
    access_token: str,
    refresh_token: str,
    expires_at: int,
    scope: Optional[str],
) -> None:
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
        (athlete_id, access_token, refresh_token, expires_at, scope),
    )


def db_get_refresh_token(conn: psycopg.Connection, athlete_id: int) -> Optional[str]:
    row = conn.execute(
        "select refresh_token from strava_tokens where athlete_id=%s",
        (athlete_id,),
    ).fetchone()
    return row[0] if row and row[0] else None


def db_list_athletes_with_refresh_tokens(conn: psycopg.Connection) -> List[Tuple[int, str]]:
    rows = conn.execute(
        """
        select athlete_id, refresh_token
        from strava_tokens
        where refresh_token is not null and refresh_token <> ''
        order by athlete_id
        """
    ).fetchall()
    return [(int(r[0]), str(r[1])) for r in rows]


def db_upsert_activity(conn: psycopg.Connection, athlete_id: int, a: Dict[str, Any]) -> Optional[int]:
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
            int(a["id"]),
            athlete_id,
            a.get("name"),
            a.get("sport_type") or a.get("type"),
            start_date,
            a.get("timezone"),
            a.get("elapsed_time"),
            a.get("moving_time"),
            a.get("distance"),
            a.get("total_elevation_gain"),
            a.get("average_speed"),
            a.get("max_speed"),
            a.get("average_heartrate"),
            a.get("max_heartrate"),
            a.get("average_watts"),
            a.get("max_watts"),
            a.get("average_cadence"),
            a.get("visibility"),
            a.get("trainer"),
            a.get("commute"),
            start_lat,
            start_lng,
            json.dumps(a),
        ),
    )

    if start_date:
        return iso_to_epoch(start_date)
    return None


def ingest_one_athlete(
    *,
    conn: psycopg.Connection,
    client_id: str,
    client_secret: str,
    athlete_id_hint: Optional[int],
    refresh_token: str,
    per_page: int,
    after_default: int,
) -> Dict[str, Any]:
    """Ingest one athlete, returns a small summary dict for logging."""

    token_data = refresh_access_token(client_id, client_secret, refresh_token)
    access_token = token_data["access_token"]
    expires_at = int(token_data.get("expires_at") or 0)
    new_refresh = token_data.get("refresh_token") or refresh_token
    scope = token_data.get("scope")

    athlete = strava_get(f"{STRAVA_API_BASE}/athlete", access_token)
    athlete_id = int(athlete["id"])

    if athlete_id_hint and athlete_id_hint != athlete_id:
        LOG.warning("Athlete id mismatch: DB/env hinted %s but token belongs to %s", athlete_id_hint, athlete_id)

    db_upsert_athlete(conn, athlete)
    db_upsert_tokens(conn, athlete_id, access_token, new_refresh, expires_at, scope)

    after_epoch = db_get_last_after_epoch(conn, athlete_id, after_default)

    LOG.info("Sync athlete=%s after_epoch=%s per_page=%s", athlete_id, after_epoch, per_page)
    activities = list_activities_since(access_token, after_epoch=after_epoch, per_page=per_page)
    LOG.info("Retrieved %s activities for athlete=%s", len(activities), athlete_id)

    max_epoch = after_epoch
    upserted = 0

    for a in activities:
        new_epoch = db_upsert_activity(conn, athlete_id, a)
        upserted += 1
        if new_epoch is not None:
            max_epoch = max(max_epoch, new_epoch)

    # advance state with margin
    advanced_to = after_epoch
    if max_epoch > after_epoch:
        advanced_to = max_epoch - 60
        db_set_last_after_epoch(conn, athlete_id, advanced_to)

    return {
        "athlete_id": athlete_id,
        "after_epoch": after_epoch,
        "advanced_to": advanced_to,
        "retrieved": len(activities),
        "upserted": upserted,
        "expires_at": expires_at,
        "scope": scope,
        "used_refresh_token_changed": (new_refresh != refresh_token),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest Strava activities into PostgreSQL (Supabase)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--athlete-id", type=int, default=None, help="Ingest only this athlete (refresh_token is read from DB)")
    g.add_argument("--all", action="store_true", help="Ingest all athletes found in strava_tokens")
    p.add_argument("--per-page", type=int, default=None, help="Strava pagination page size (default: env STRAVA_PER_PAGE or 50)")
    p.add_argument(
        "--after-default",
        type=int,
        default=None,
        help="Default epoch cursor when no state exists (default: env STRAVA_AFTER_EPOCH_DEFAULT or 0)",
    )
    return p.parse_args()


def main() -> None:
    # Load env from repo root (.env then .env.local overrides)
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env")
    load_dotenv(root / ".env.local")

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    args = parse_args()

    db_url = must_env("DATABASE_URL")
    client_id = must_env("STRAVA_CLIENT_ID")
    client_secret = must_env("STRAVA_CLIENT_SECRET")

    per_page = args.per_page or int(os.getenv("STRAVA_PER_PAGE", "50"))
    after_default = args.after_default or int(os.getenv("STRAVA_AFTER_EPOCH_DEFAULT", "0"))

    with psycopg.connect(db_url) as conn:
        conn.execute("set timezone to 'UTC';")

        # Choose athletes to ingest
        targets: List[Tuple[Optional[int], str]] = []

        if args.all:
            rows = db_list_athletes_with_refresh_tokens(conn)
            if not rows:
                raise RuntimeError("No athletes with refresh tokens found in strava_tokens")
            targets = [(ath_id, rt) for ath_id, rt in rows]
            LOG.info("Multi-athlete ingestion: %s athletes", len(targets))

        elif args.athlete_id is not None:
            rt = db_get_refresh_token(conn, args.athlete_id)
            if not rt:
                raise RuntimeError(f"No refresh_token found in DB for athlete_id={args.athlete_id}")
            targets = [(args.athlete_id, rt)]

        else:
            # Backward-compatible single-athlete mode using env STRAVA_REFRESH_TOKEN
            rt = must_env("STRAVA_REFRESH_TOKEN")
            targets = [(None, rt)]

        summaries: List[Dict[str, Any]] = []

        for athlete_hint, refresh_token in targets:
            try:
                summary = ingest_one_athlete(
                    conn=conn,
                    client_id=client_id,
                    client_secret=client_secret,
                    athlete_id_hint=athlete_hint,
                    refresh_token=refresh_token,
                    per_page=per_page,
                    after_default=after_default,
                )
                conn.commit()
                summaries.append(summary)
                LOG.info(
                    "✅ athlete=%s retrieved=%s advanced_to=%s",
                    summary["athlete_id"],
                    summary["retrieved"],
                    summary["advanced_to"],
                )
            except Exception as e:
                conn.rollback()
                LOG.exception("❌ Failed ingest for athlete_hint=%s: %s", athlete_hint, e)

        LOG.info("Done. %s athlete(s) processed.", len(summaries))


if __name__ == "__main__":
    main()
