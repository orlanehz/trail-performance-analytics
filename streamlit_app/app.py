from __future__ import annotations

import math
from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.config import get_settings

st.set_page_config(page_title="Trail Performance Analytics", layout="wide")

DATA_PATH = ROOT / "notebooks" / "data" / "processed" / "dataset_model.parquet"
TARGET = "pace_s_per_km"
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


@st.cache_data
def load_dataset(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_parquet(path)


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


def render_analysis_page(df: pd.DataFrame | None):
    st.title("Trail Performance Analytics")
    st.caption("Analyse et prediction de l'allure a partir des donnees Strava")

    if df is None:
        st.info("Aucun dataset trouve. Ajoute `notebooks/data/processed/dataset_model.parquet`.")
        return

    st.subheader("Resume du dataset")
    cols = st.columns(4)
    cols[0].metric("Activites", f"{len(df):d}")
    if "start_date" in df.columns and not df["start_date"].isna().all():
        cols[1].metric("Debut", str(df["start_date"].min().date()))
        cols[2].metric("Fin", str(df["start_date"].max().date()))
    if "distance_m" in df.columns:
        cols[3].metric("Distance moy.", f"{df['distance_m'].mean() / 1000:.1f} km")

    st.subheader("Visualisations")
    if "pace_s_per_km" in df.columns:
        fig_pace = px.histogram(
            df,
            x="pace_s_per_km",
            nbins=20,
            title="Distribution de l'allure (sec/km)",
        )
        st.plotly_chart(fig_pace, use_container_width=True)

    if {"distance_m", "pace_s_per_km"}.issubset(df.columns):
        fig_scatter = px.scatter(
            df,
            x="distance_m",
            y="pace_s_per_km",
            color="elev_density_m_per_km" if "elev_density_m_per_km" in df.columns else None,
            labels={"distance_m": "Distance (m)", "pace_s_per_km": "Allure (sec/km)"},
            title="Distance vs allure",
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    st.subheader("Prediction pour la prochaine course")
    model, metrics = train_model(df)
    if model is None:
        st.warning("Le modele ne peut pas etre entraine avec ce dataset.")
        return

    if metrics:
        st.caption(
            f"Evaluation rapide (split temporel): MAE {metrics['mae']:.1f} s/km, "
            f"RMSE {metrics['rmse']:.1f} s/km"
        )

    with st.form("prediction_form"):
        col1, col2 = st.columns(2)
        distance_km = col1.number_input("Distance de la course (km)", min_value=0.1, value=10.0)
        elevation_gain_m = col2.number_input("D+ de la course (m)", min_value=0.0, value=300.0)

        st.markdown("**Charge recente (7 jours)**")
        col3, col4, col5 = st.columns(3)
        dist_7d_km = col3.number_input("Distance 7j (km)", min_value=0.0, value=20.0)
        elev_7d_m = col4.number_input("D+ 7j (m)", min_value=0.0, value=400.0)
        time_7d_h = col5.number_input("Temps 7j (h)", min_value=0.0, value=3.0)

        st.markdown("**Charge recente (28 jours)**")
        col6, col7, col8 = st.columns(3)
        dist_28d_km = col6.number_input("Distance 28j (km)", min_value=0.0, value=80.0)
        elev_28d_m = col7.number_input("D+ 28j (m)", min_value=0.0, value=1600.0)
        time_28d_h = col8.number_input("Temps 28j (h)", min_value=0.0, value=12.0)

        submitted = st.form_submit_button("Predire")

    if submitted:
        features = build_features(
            distance_km=distance_km,
            elevation_gain_m=elevation_gain_m,
            dist_7d_km=dist_7d_km,
            elev_7d_m=elev_7d_m,
            time_7d_h=time_7d_h,
            dist_28d_km=dist_28d_km,
            elev_28d_m=elev_28d_m,
            time_28d_h=time_28d_h,
        )
        pred_pace = float(model.predict(features)[0])
        pred_time = pred_pace * distance_km

        st.success(
            f"Allure estimee: {format_seconds(pred_pace)} min/km "
            f"(~{pred_pace:.0f} s/km)"
        )
        st.info(f"Temps estime: {format_seconds(pred_time)} pour {distance_km:.1f} km")


def render_strava_page(settings):
    st.title("Connexion Strava")
    st.caption("Autoriser l'acces a vos activites via OAuth")

    st.subheader("Etapes")
    st.markdown(
        """
1. Creez une application Strava sur https://www.strava.com/settings/api
2. Definissez un `Authorization Callback Domain` (ex: `localhost`)
3. Renseignez `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` et `STRAVA_REDIRECT_URI` dans `.env`
4. Cliquez sur le lien d'autorisation ci-dessous pour donner votre consentement
"""
    )

    client_id = settings.strava_client_id
    redirect_uri = settings.strava_redirect_uri

    if client_id and redirect_uri:
        auth_url = (
            "https://www.strava.com/oauth/authorize"
            f"?client_id={client_id}"
            "&response_type=code"
            f"&redirect_uri={redirect_uri}"
            "&scope=read,activity:read_all"
            "&approval_prompt=auto"
        )
        st.link_button("Autoriser Strava", auth_url)
    else:
        st.warning("Complete `STRAVA_CLIENT_ID` et `STRAVA_REDIRECT_URI` pour generer le lien.")

    st.subheader("Recuperer le code")
    st.markdown(
        """
Apres acceptation, Strava redirige vers votre `redirect_uri` avec un parametre `code`.
Ce code doit etre echange contre un `access_token` (serveur ou script local).

Exemple (a adapter) :
```
curl -X POST https://www.strava.com/oauth/token \\
  -d client_id=YOUR_ID \\
  -d client_secret=YOUR_SECRET \\
  -d code=AUTH_CODE \\
  -d grant_type=authorization_code
```
"""
    )


settings = get_settings()

st.sidebar.title("Navigation")
page = st.sidebar.radio("Pages", ["Analyse & Prediction", "Connexion Strava"])

df = load_dataset(DATA_PATH)

if page == "Analyse & Prediction":
    render_analysis_page(df)
else:
    render_strava_page(settings)
