from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from shared import format_seconds, get_database_url, is_admin_enabled, load_dataset_from_db, prepare_features, require_admin


def render_admin_login() -> None:
    if not is_admin_enabled():
        st.warning("Le mode admin n'est pas active. Ajoute `ADMIN_PASSWORD` dans les secrets.")
        return

    if st.session_state.get("is_admin", False):
        st.success("Connecte (admin)")
        if st.button("Se deconnecter"):
            st.session_state["is_admin"] = False
            st.rerun()
        return

    pwd = st.text_input("Mot de passe admin", type="password")
    if st.button("Se connecter"):
        if pwd == st.secrets.get("ADMIN_PASSWORD"):
            st.session_state["is_admin"] = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect")


st.title("Admin — Comparer deux athletes")
st.caption("Acces reserve : comparaison de volumes, charge et allure")

render_admin_login()
require_admin()

database_url = get_database_url()
if not database_url:
    st.info("Configure `DATABASE_URL` pour charger les donnees.")
    st.stop()

try:
    df = load_dataset_from_db(database_url)
    df = prepare_features(df)
except Exception as exc:
    st.error(f"Erreur DB: {exc}")
    st.stop()

if df is None or df.empty:
    st.info("Aucune donnee disponible. Verifie la table `activity_features`.")
    st.stop()

if "athlete_id" not in df.columns or df["athlete_id"].isna().all():
    st.info("Impossible de comparer : aucune colonne athlete_id dans le dataset.")
    st.stop()

athlete_ids = sorted(df["athlete_id"].dropna().unique().tolist())
if len(athlete_ids) < 2:
    st.info("Il faut au moins 2 athletes ingeres pour utiliser la comparaison.")
    st.stop()

colA, colB = st.columns(2)
a_id = colA.selectbox("Athlete A", athlete_ids, index=0, key="compare_a")
b_id = colB.selectbox("Athlete B", athlete_ids, index=1, key="compare_b")

dfA = df[df["athlete_id"] == a_id].copy()
dfB = df[df["athlete_id"] == b_id].copy()

if "start_date" in dfA.columns:
    dfA["start_date"] = pd.to_datetime(dfA["start_date"], utc=True, errors="coerce")
if "start_date" in dfB.columns:
    dfB["start_date"] = pd.to_datetime(dfB["start_date"], utc=True, errors="coerce")

window_days = st.slider("Fenetre d'analyse (jours)", min_value=7, max_value=180, value=28, step=7)


def window_view(d: pd.DataFrame) -> pd.DataFrame:
    if "start_date" not in d.columns or d["start_date"].isna().all():
        return d
    end = d["start_date"].max()
    start = end - pd.Timedelta(days=window_days)
    return d[(d["start_date"] >= start) & (d["start_date"] <= end)]


wA = window_view(dfA)
wB = window_view(dfB)


def summarize(d: pd.DataFrame) -> dict:
    if d.empty:
        return {"activities": 0, "dist_km": 0.0, "elev_m": 0.0, "pace_med": np.nan}
    dist_km = float((d.get("distance_m") or 0).sum() / 1000.0) if "distance_m" in d.columns else 0.0
    elev_m = float((d.get("elevation_gain_m") or 0).sum()) if "elevation_gain_m" in d.columns else 0.0
    pace_med = float(d["pace_s_per_km"].median()) if "pace_s_per_km" in d.columns else np.nan
    return {"activities": int(len(d)), "dist_km": dist_km, "elev_m": elev_m, "pace_med": pace_med}


sA = summarize(wA)
sB = summarize(wB)

st.subheader(f"Resume sur les {window_days} derniers jours")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Activites", f"{sA['activities']} vs {sB['activities']}")
m2.metric("Distance", f"{sA['dist_km']:.1f} km vs {sB['dist_km']:.1f} km")
m3.metric("D+", f"{sA['elev_m']:.0f} m vs {sB['elev_m']:.0f} m")
if not np.isnan(sA["pace_med"]) and not np.isnan(sB["pace_med"]):
    m4.metric("Allure mediane", f"{format_seconds(sA['pace_med'])} vs {format_seconds(sB['pace_med'])}")
else:
    m4.metric("Allure mediane", "n/a")

st.subheader("Courbes")
plot_cols = [c for c in ["start_date", "distance_m", "elevation_gain_m", "pace_s_per_km"] if c in df.columns]
pA = dfA[plot_cols].copy()
pB = dfB[plot_cols].copy()
pA["athlete"] = f"A ({a_id})"
pB["athlete"] = f"B ({b_id})"
p = pd.concat([pA, pB], ignore_index=True)

if "start_date" in p.columns and "distance_m" in p.columns:
    st.plotly_chart(
        px.line(p, x="start_date", y="distance_m", color="athlete", title="Distance par sortie (m)"),
        use_container_width=True,
    )

if "start_date" in p.columns and "elevation_gain_m" in p.columns:
    st.plotly_chart(
        px.line(p, x="start_date", y="elevation_gain_m", color="athlete", title="D+ par sortie (m)"),
        use_container_width=True,
    )

if "start_date" in p.columns and "pace_s_per_km" in p.columns:
    st.plotly_chart(
        px.line(p, x="start_date", y="pace_s_per_km", color="athlete", title="Allure (sec/km)"),
        use_container_width=True,
    )

st.subheader("Donnees (echantillon)")
st.dataframe(p.sort_values("start_date", ascending=False).head(50), use_container_width=True)
