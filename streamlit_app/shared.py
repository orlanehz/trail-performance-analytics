from __future__ import annotations

import json
import math
import os
from typing import Any

import numpy as np
import pandas as pd
import requests
import streamlit as st

TARGET = "pace_s_per_km"
MODEL_NAME = "random_forest"
MODEL_VERSION = "v1"
FEATURES = [
    "distance_m",
    "elevation_gain_m",
    "dist_7d_m",
    "elev_7d_m",
    "time_7d_s",
    "dist_28d_m",
    "elev_28d_m",
    "time_28d_s",
    "elev_density_m_per_m",
    "charge_ratio_dist_7_28",
    "charge_ratio_elev_7_28",
    "charge_ratio_time_7_28",
    "log_distance_m",
    "log_elev_gain_m",
]


# Admin / Coach mode

def is_admin_enabled() -> bool:
    try:
        return bool(st.secrets.get("ADMIN_PASSWORD"))
    except Exception:
        return False


def require_admin() -> None:
    if not st.session_state.get("is_admin", False):
        st.warning("Acces reserve (mode coach/admin).")
        st.stop()

def require_google_login() -> None:
    if not getattr(st, "user", None) or not st.user.is_logged_in:
        st.title("Connexion")
        st.write("Connecte-toi pour accéder à l’application.")
        st.button("Se connecter avec Google", on_click=st.login)
        st.stop()

def require_strava_connected(db, user_id):
    token = db.get_oauth_token(user_id=user_id, provider="strava")
    if not token:
        st.warning("Connecte Strava pour accéder à tes analyses.")
        st.page_link("pages/02_Connecter_Strava.py", label="➡️ Connecter Strava")
        st.stop()


# --- Google user identity helpers ---

def get_google_identity() -> dict[str, str | None]:
    """Return best-effort identity fields from Streamlit OIDC user."""
    email = getattr(st.user, "email", None)
    name = getattr(st.user, "name", None)
    user_id = getattr(st.user, "id", None) or email
    return {
        "provider_user_id": str(user_id) if user_id is not None else None,
        "email": email,
        "name": name,
    }


def ensure_app_user() -> int:
    """Ensure the logged-in Google user exists in `app_users` and return `app_users.id`.

    This is the canonical way to 'load users into app_users': on first login we upsert.
    The resulting `app_user_id` is cached in `st.session_state`.
    """
    require_google_login()

    if st.session_state.get("app_user_id"):
        return int(st.session_state["app_user_id"])

    database_url = get_database_url()
    if not database_url:
        st.error("DATABASE_URL manquant. Ajoute-le dans les secrets.")
        st.stop()

    ident = get_google_identity()
    provider_user_id = ident.get("provider_user_id")
    if not provider_user_id:
        st.error(
            "Impossible d'identifier l'utilisateur Google (id/email manquant). "
            "Vérifie la configuration OIDC et les scopes."
        )
        st.stop()

    app_user_id = upsert_app_user(
        database_url=database_url,
        provider="google",
        provider_user_id=provider_user_id,
        email=ident.get("email"),
        name=ident.get("name"),
        raw={
            "email": ident.get("email"),
            "name": ident.get("name"),
            "id": provider_user_id,
        },
    )

    st.session_state["app_user_id"] = int(app_user_id)
    return int(app_user_id)

def get_database_url() -> str | None:
    try:
        if "DATABASE_URL" in st.secrets:
            return st.secrets["DATABASE_URL"]
    except Exception:
        pass
    return os.getenv("DATABASE_URL")


def get_secret(name: str) -> str | None:
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name)


def get_user_summary(database_url: str, user_id: int) -> dict[str, Any] | None:
    import psycopg

    with psycopg.connect(database_url) as conn:
        row = conn.execute(
            "select id, email, name from app_users where id = %s",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return {"id": int(row[0]), "email": row[1], "name": row[2]}


def has_oauth_token(database_url: str, user_id: int, provider: str) -> bool:
    import psycopg

    with psycopg.connect(database_url) as conn:
        row = conn.execute(
            "select 1 from oauth_tokens where user_id = %s and provider = %s limit 1",
            (user_id, provider),
        ).fetchone()
    return row is not None


def render_profile_badge() -> None:
    if not getattr(st, "user", None) or not st.user.is_logged_in:
        st.info("Profil non connecte")
        return

    name = getattr(st.user, "name", None)
    email = getattr(st.user, "email", None)
    label = name or email or "Utilisateur connecte"
    st.success(f"Profil connecte : {label}")


@st.cache_data(ttl=600)
def load_dataset_from_db(database_url: str) -> pd.DataFrame:
    import psycopg

    query = """
        select
            activity_id, athlete_id, start_date, distance_m, elevation_gain_m, pace_s_per_km,
            dist_7d_m, elev_7d_m, time_7d_s,
            dist_28d_m, elev_28d_m, time_28d_s
        from activity_features
        order by start_date
    """
    with psycopg.connect(database_url) as conn:
        return pd.read_sql_query(query, conn)


@st.cache_resource
def train_model(df: pd.DataFrame):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error, mean_squared_error

    df = df.dropna(subset=[TARGET] + FEATURES).copy()
    if df.empty:
        return None, {}

    if "start_date" in df.columns:
        df = df.sort_values("start_date")

    split_idx = max(1, int(len(df) * 0.8))
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:] if split_idx < len(df) else pd.DataFrame()

    model = RandomForestRegressor(n_estimators=250, random_state=42)
    model.fit(train_df[FEATURES], train_df[TARGET])

    metrics = {}
    if not test_df.empty:
        preds = model.predict(test_df[FEATURES])
        metrics = {
            "mae": mean_absolute_error(test_df[TARGET], preds),
            "rmse": math.sqrt(mean_squared_error(test_df[TARGET], preds)),
        }

    return model, metrics


def format_seconds(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:d}:{secs:02d}"


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    distance_m = df["distance_m"].replace(0, np.nan)
    elev_gain = df["elevation_gain_m"].replace(0, np.nan)

    df["elev_density_m_per_m"] = df["elevation_gain_m"] / distance_m
    df["elev_density_m_per_km"] = df["elev_density_m_per_m"] * 1000.0

    df["charge_ratio_dist_7_28"] = df["dist_7d_m"] / df["dist_28d_m"].replace(0, np.nan)
    df["charge_ratio_elev_7_28"] = df["elev_7d_m"] / df["elev_28d_m"].replace(0, np.nan)
    df["charge_ratio_time_7_28"] = df["time_7d_s"] / df["time_28d_s"].replace(0, np.nan)

    df["log_distance_m"] = np.log(distance_m.fillna(0) + 1.0)
    df["log_elev_gain_m"] = np.log(elev_gain.fillna(0) + 1.0)

    df.replace([np.inf, -np.inf], np.nan, inplace=True)

    return df


def save_prediction(
    database_url: str,
    athlete_id: int,
    activity_id: int | None,
    prediction_type: str,
    predicted_pace_s_per_km: float,
    predicted_time_s: float,
    features: dict,
):
    import json
    import psycopg

    with psycopg.connect(database_url) as conn:
        if activity_id is None:
            conn.execute(
                """
                insert into model_predictions (
                  athlete_id, activity_id, prediction_type,
                  predicted_pace_s_per_km, predicted_time_s,
                  model_name, model_version, features
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    athlete_id,
                    None,
                    prediction_type,
                    predicted_pace_s_per_km,
                    predicted_time_s,
                    MODEL_NAME,
                    MODEL_VERSION,
                    json.dumps(features),
                ),
            )
        else:
            conn.execute(
                """
                insert into model_predictions (
                  athlete_id, activity_id, prediction_type,
                  predicted_pace_s_per_km, predicted_time_s,
                  model_name, model_version, features
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                on conflict (athlete_id, activity_id, prediction_type, model_version)
                do update set
                  predicted_pace_s_per_km = excluded.predicted_pace_s_per_km,
                  predicted_time_s = excluded.predicted_time_s,
                  model_name = excluded.model_name,
                  features = excluded.features,
                  created_at = now()
                """,
                (
                    athlete_id,
                    activity_id,
                    prediction_type,
                    predicted_pace_s_per_km,
                    predicted_time_s,
                    MODEL_NAME,
                    MODEL_VERSION,
                    json.dumps(features),
                ),
            )
        conn.commit()


def upsert_app_user(
    database_url: str,
    provider: str,
    provider_user_id: str,
    email: str | None,
    name: str | None,
    raw: dict[str, Any],
) -> int:
    import psycopg

    with psycopg.connect(database_url) as conn:
        row = conn.execute(
            """
            insert into app_users (provider, provider_user_id, email, name, raw)
            values (%s, %s, %s, %s, %s::jsonb)
            on conflict (provider, provider_user_id) do update set
              email = excluded.email,
              name = excluded.name,
              raw = excluded.raw,
              updated_at = now()
            returning id
            """,
            (provider, provider_user_id, email, name, json.dumps(raw)),
        ).fetchone()
        conn.commit()
        return int(row[0])


def upsert_oauth_token(
    database_url: str,
    user_id: int,
    provider: str,
    access_token: str,
    refresh_token: str | None,
    expires_at: int | None,
    scope: str | None,
    raw: dict[str, Any],
) -> None:
    import psycopg

    with psycopg.connect(database_url) as conn:
        conn.execute(
            """
            insert into oauth_tokens (
              user_id, provider, access_token, refresh_token, expires_at, scope, raw
            )
            values (%s, %s, %s, %s, %s, %s, %s::jsonb)
            on conflict (user_id, provider) do update set
              access_token = excluded.access_token,
              refresh_token = excluded.refresh_token,
              expires_at = excluded.expires_at,
              scope = excluded.scope,
              raw = excluded.raw,
              updated_at = now()
            """,
            (
                user_id,
                provider,
                access_token,
                refresh_token,
                expires_at,
                scope,
                json.dumps(raw),
            ),
        )
        conn.commit()


def exchange_strava_code(code: str, client_id: str, client_secret: str) -> dict[str, Any]:
    r = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def fetch_strava_athlete(access_token: str) -> dict[str, Any]:
    r = requests.get(
        "https://www.strava.com/api/v3/athlete",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def exchange_google_code(
    code: str, client_id: str, client_secret: str, redirect_uri: str
) -> dict[str, Any]:
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def fetch_google_profile(access_token: str) -> dict[str, Any]:
    r = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def build_features(
    distance_km: float,
    elevation_gain_m: float,
    dist_7d_km: float,
    elev_7d_m: float,
    time_7d_h: float,
    dist_28d_km: float,
    elev_28d_m: float,
    time_28d_h: float,
) -> pd.DataFrame:
    distance_m = distance_km * 1000.0
    dist_7d_m = dist_7d_km * 1000.0
    dist_28d_m = dist_28d_km * 1000.0
    time_7d_s = time_7d_h * 3600.0
    time_28d_s = time_28d_h * 3600.0

    elev_density = (elevation_gain_m / distance_m) if distance_m > 0 else 0.0
    charge_ratio_dist = (dist_7d_m / dist_28d_m) if dist_28d_m > 0 else 0.0
    charge_ratio_elev = (elev_7d_m / elev_28d_m) if elev_28d_m > 0 else 0.0
    charge_ratio_time = (time_7d_s / time_28d_s) if time_28d_s > 0 else 0.0

    features = {
        "distance_m": distance_m,
        "elevation_gain_m": elevation_gain_m,
        "dist_7d_m": dist_7d_m,
        "elev_7d_m": elev_7d_m,
        "time_7d_s": time_7d_s,
        "dist_28d_m": dist_28d_m,
        "elev_28d_m": elev_28d_m,
        "time_28d_s": time_28d_s,
        "elev_density_m_per_m": elev_density,
        "charge_ratio_dist_7_28": charge_ratio_dist,
        "charge_ratio_elev_7_28": charge_ratio_elev,
        "charge_ratio_time_7_28": charge_ratio_time,
        "log_distance_m": math.log(distance_m + 1.0),
        "log_elev_gain_m": math.log(elevation_gain_m + 1.0),
    }
    return pd.DataFrame([features])
