from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from shared import build_features, format_seconds, get_database_url, load_dataset_from_db, prepare_features, save_prediction, train_model


def render_page(df: pd.DataFrame | None, database_url: str | None) -> None:
    st.title("Trail Performance Analytics")
    st.caption("Analyse et prediction de l'allure a partir des donnees Strava")

    if df is None:
        st.info("Aucun dataset trouve. Configure `DATABASE_URL` et verifie la table `activity_features`.")
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
        athlete_id = None
        if "athlete_id" in df.columns and df["athlete_id"].notna().any():
            athlete_ids = sorted(df["athlete_id"].dropna().unique().tolist())
            athlete_id = st.selectbox("Athlete", athlete_ids)
        else:
            athlete_id = st.number_input("Athlete ID", min_value=0, value=0, step=1)

        activity_id = st.number_input(
            "Activity ID (optionnel)", min_value=0, value=0, step=1
        )
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
        features_df = build_features(
            distance_km=distance_km,
            elevation_gain_m=elevation_gain_m,
            dist_7d_km=dist_7d_km,
            elev_7d_m=elev_7d_m,
            time_7d_h=time_7d_h,
            dist_28d_km=dist_28d_km,
            elev_28d_m=elev_28d_m,
            time_28d_h=time_28d_h,
        )
        pred_pace = float(model.predict(features_df)[0])
        pred_time = pred_pace * distance_km

        st.session_state["last_prediction"] = {
            "athlete_id": int(athlete_id),
            "activity_id": int(activity_id) if activity_id else None,
            "prediction_type": "race_time",
            "predicted_pace_s_per_km": float(pred_pace),
            "predicted_time_s": float(pred_time),
            "features": features_df.iloc[0].to_dict(),
        }

        st.success(
            f"Allure estimee: {format_seconds(pred_pace)} min/km "
            f"(~{pred_pace:.0f} s/km)"
        )
        st.info(f"Temps estime: {format_seconds(pred_time)} pour {distance_km:.1f} km")

    if database_url and "last_prediction" in st.session_state:
        st.divider()
        st.subheader("Sauvegarder la prediction")
        st.caption("Enregistre la derniere prediction calculee dans la table `model_predictions`.")
        if st.button("💾 Sauvegarder la derniere prediction"):
            p = st.session_state["last_prediction"]
            save_prediction(
                database_url=database_url,
                athlete_id=p["athlete_id"],
                activity_id=p["activity_id"],
                prediction_type=p["prediction_type"],
                predicted_pace_s_per_km=p["predicted_pace_s_per_km"],
                predicted_time_s=p["predicted_time_s"],
                features=p["features"],
            )
            st.success("✅ Prediction sauvegardee dans la base.")


database_url = get_database_url()
df = None
if database_url:
    try:
        df = load_dataset_from_db(database_url)
        df = prepare_features(df)
    except Exception as exc:
        st.sidebar.warning(f"Erreur DB: {exc}")

render_page(df, database_url)
