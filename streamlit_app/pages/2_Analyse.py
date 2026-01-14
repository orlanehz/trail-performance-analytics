from __future__ import annotations

import json
import logging
import os
import platform
import time
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from streamlit.runtime.scriptrunner.script_run_context import get_script_run_ctx

_logger = logging.getLogger(__name__)


def is_admin_enabled() -> bool:
    """Return True if admin allowlist is configured in secrets."""
    try:
        raw = st.secrets.get("ADMIN_EMAILS", "")
        allowed = {e.strip().lower() for e in str(raw).split(",") if e.strip()}
        return len(allowed) > 0
    except Exception:
        return False


def is_admin_user(email: str | None) -> bool:
    """Return True if the given email is in the ADMIN_EMAILS allowlist."""
    if not email:
        return False
    try:
        raw = st.secrets.get("ADMIN_EMAILS", "")
        allowed = {e.strip().lower() for e in str(raw).split(",") if e.strip()}
        return email.strip().lower() in allowed
    except Exception:
        return False


def ensure_app_user() -> int:
    # Dummy implementation; replace with actual user management
    return 1


def get_database_url() -> str | None:
    return os.getenv("DATABASE_URL")


def has_oauth_token(database_url: str, user_id: int, provider: str) -> bool:
    # Dummy implementation; replace with actual token check
    return True


def load_dataset_from_db(database_url: str) -> pd.DataFrame:
    # Dummy implementation; replace with actual DB loading
    return pd.DataFrame()


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    # Dummy implementation; replace with actual feature preparation
    return df


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
    # Dummy implementation; replace with actual feature building
    return pd.DataFrame(
        [
            {
                "distance_km": distance_km,
                "elevation_gain_m": elevation_gain_m,
                "dist_7d_km": dist_7d_km,
                "elev_7d_m": elev_7d_m,
                "time_7d_h": time_7d_h,
                "dist_28d_km": dist_28d_km,
                "elev_28d_m": elev_28d_m,
                "time_28d_h": time_28d_h,
            }
        ]
    )


def train_model(df: pd.DataFrame) -> tuple[Any, dict[str, float]]:
    # Dummy implementation; replace with actual model training
    model = None
    metrics = {"mae": 10.0, "rmse": 15.0}
    return model, metrics


def save_prediction(
    database_url: str,
    user_id: int,
    athlete_id: int | None,
    activity_id: int | None,
    prediction_type: str,
    predicted_pace_s_per_km: float,
    predicted_time_s: float,
    features: dict[str, Any],
) -> None:
    # Dummy implementation; replace with actual save logic
    pass


def format_seconds(seconds: float) -> str:
    # Format seconds into mm:ss string
    m, s = divmod(int(round(seconds)), 60)
    return f"{m}:{s:02d}"


def require_google_login() -> None:
    # Dummy implementation; replace with actual login requirement
    pass


def render_profile_badge() -> None:
    # Dummy implementation; replace with actual profile badge rendering
    pass


def render_sidebar(app_user_id: int, strava_connected: bool) -> None:
    st.sidebar.title("Menu")
    st.sidebar.page_link("pages/0_Dashboard.py", label="🏠 Tableau de bord")
    st.sidebar.page_link("pages/2_Analyse.py", label="📊 Analyse")
    st.sidebar.page_link("pages/3_Predictions.py", label="🧠 Predictions")
    st.sidebar.page_link("pages/4_Parametres.py", label="⚙️ Parametres")

    if not strava_connected:
        st.sidebar.page_link("pages/5_Connexion_Strava.py", label="🔗 Connexion Strava")

    # Admin (visible only to allowlisted emails)
    email = getattr(st.user, "email", None)
    if is_admin_user(email):
        st.sidebar.page_link("pages/9_Admin.py", label="🛠 Administration")

    st.sidebar.button("Se deconnecter")
