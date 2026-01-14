from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from shared import (
    ensure_app_user,
    get_database_url,
    get_prediction_history,
    has_oauth_token,
    render_profile_badge,
    render_sidebar,
    require_google_login,
)


require_google_login()
app_user_id = ensure_app_user()

render_profile_badge()

database_url = get_database_url()
strava_connected = False
if database_url:
    strava_connected = has_oauth_token(database_url, app_user_id, "strava")

render_sidebar(app_user_id, strava_connected)

st.title("Predictions")
st.caption("Historique des predictions sauvegardees")

if not database_url:
    st.warning("DATABASE_URL manquant.")
    st.stop()

try:
    df = get_prediction_history(database_url, app_user_id)
except Exception as exc:
    st.error(f"Erreur DB: {exc}")
    st.stop()

if df is None or df.empty:
    st.info("Aucune prediction enregistree.")
    st.stop()

# Expand features for display
def _features_to_dict(value):
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {}


if "features" in df.columns:
    df["features"] = df["features"].apply(_features_to_dict)
    df["distance_m"] = df["features"].apply(lambda x: x.get("distance_m"))
    df["elevation_gain_m"] = df["features"].apply(lambda x: x.get("elevation_gain_m"))

show_cols = [
    c
    for c in [
        "created_at",
        "prediction_type",
        "distance_m",
        "elevation_gain_m",
        "predicted_pace_s_per_km",
        "predicted_time_s",
    ]
    if c in df.columns
]

st.dataframe(df[show_cols], use_container_width=True)

st.subheader("Dupliquer une prediction")
idx = st.number_input("Index a dupliquer", min_value=0, max_value=len(df) - 1, value=0)
row = df.iloc[int(idx)]

if st.button("Pre-remplir dans Analyse"):
    st.session_state["prefill_prediction"] = {
        "distance_km": float(row.get("distance_m") or 0) / 1000.0,
        "elevation_gain_m": float(row.get("elevation_gain_m") or 0),
    }
    st.switch_page("pages/2_Analyse.py")
