from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from shared import (
    ensure_app_user,
    format_seconds,
    get_database_url,
    get_dashboard_kpis,
    has_oauth_token,
    load_dataset_from_db,
    prepare_features,
    render_profile_badge,
    render_sidebar,
    require_google_login,
)


@st.cache_data(ttl=600, show_spinner=False)
def _load_prepared_dataset(database_url: str) -> pd.DataFrame:
    df = load_dataset_from_db(database_url)
    df = prepare_features(df)
    return df


require_google_login()
app_user_id = ensure_app_user()

render_profile_badge()

database_url = get_database_url()
strava_connected = False
if database_url:
    strava_connected = has_oauth_token(database_url, app_user_id, "strava")

render_sidebar(app_user_id, strava_connected)

st.title("Dashboard")
st.caption("Vue synthese des performances")

if not strava_connected:
    st.warning("Strava n'est pas connecte. Connecte Strava pour acceder au dashboard.")
    st.page_link("pages/5_Connexion_Strava.py", label="➡️ Connecter Strava")
    st.stop()

if not database_url:
    st.warning("DATABASE_URL manquant. Ajoute-le dans les secrets Streamlit Cloud.")
    st.stop()

try:
    df = _load_prepared_dataset(database_url)
except Exception as exc:
    st.error(f"Erreur DB: {exc}")
    st.stop()

if df is None or df.empty:
    st.info("Aucune donnee disponible.")
    st.stop()

kpis = get_dashboard_kpis(database_url)

st.subheader("KPIs")
cols = st.columns(4)
cols[0].metric("Activites", f"{kpis['activities']}")
cols[1].metric("Km 28j", f"{kpis['dist_28d_m'] / 1000:.1f}")
cols[2].metric("D+ 28j", f"{kpis['elev_28d_m']:.0f}")
if kpis["pace_avg"] is not None:
    cols[3].metric("Allure moyenne", format_seconds(kpis["pace_avg"]))
else:
    cols[3].metric("Allure moyenne", "—")

st.subheader("Graphiques")

if {"start_date", "pace_s_per_km"}.issubset(df.columns):
    fig_time = px.line(
        df.sort_values("start_date"),
        x="start_date",
        y="pace_s_per_km",
        title="Allure dans le temps",
        labels={"start_date": "Date", "pace_s_per_km": "Allure (sec/km)"},
    )
    st.plotly_chart(fig_time, use_container_width=True)

if {"start_date", "distance_m"}.issubset(df.columns):
    df_week = df.copy()
    df_week["week"] = pd.to_datetime(df_week["start_date"]).dt.to_period("W").dt.start_time
    weekly = df_week.groupby("week", as_index=False)["distance_m"].sum()
    fig_volume = px.bar(
        weekly,
        x="week",
        y="distance_m",
        title="Volume hebdo (m)",
        labels={"week": "Semaine", "distance_m": "Distance (m)"},
    )
    st.plotly_chart(fig_volume, use_container_width=True)

if "pace_s_per_km" in df.columns:
    fig_hist = px.histogram(
        df,
        x="pace_s_per_km",
        nbins=20,
        title="Distribution de l'allure",
    )
    st.plotly_chart(fig_hist, use_container_width=True)

st.subheader("Insights")
insights = []
if "charge_ratio_dist_7_28" in df.columns:
    ratio = float(df["charge_ratio_dist_7_28"].iloc[-1]) if not df.empty else 0.0
    if ratio > 1.2:
        insights.append("Ta charge 7j est elevee vs 28j (+20% ou plus).")
    elif ratio < 0.8:
        insights.append("Ta charge 7j est basse vs 28j (-20% ou plus).")
if "elev_density_m_per_km" in df.columns and "pace_s_per_km" in df.columns:
    corr = df[["elev_density_m_per_km", "pace_s_per_km"]].corr().iloc[0, 1]
    insights.append(f"Plus de D+/km semble ralentir l'allure (corr {corr:.2f}).")

if not insights:
    insights.append("Pas assez de signal pour des insights automatiques.")

for item in insights[:3]:
    st.write(f"- {item}")

st.subheader("Actions")
cols = st.columns(2)
if cols[0].button("Faire une prediction"):
    st.switch_page("pages/2_Analyse.py")
if cols[1].button("Ouvrir Analyse"):
    st.switch_page("pages/2_Analyse.py")
