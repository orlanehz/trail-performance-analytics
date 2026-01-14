from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from shared import (
    build_features,
    ensure_app_user,
    format_seconds,
    get_database_url,
    load_dataset_from_db,
    prepare_features,
    require_google_login,
    save_prediction,
    train_model,
)

@st.cache_data(ttl=600, show_spinner=False)
def _load_prepared_dataset(database_url: str) -> pd.DataFrame:
    df = load_dataset_from_db(database_url)
    df = prepare_features(df)
    return df

def render_page(df: pd.DataFrame | None, database_url: str | None, app_user_id: int) -> None:
    st.title("Analyse")
    st.caption("Analyse et prédiction d'allure à partir des données Strava")

    # --- Sidebar UX ---
    with st.sidebar:
        st.subheader("Compte")
        st.caption(f"User ID: {app_user_id}")
        st.page_link("../streamlit_app/app.py", label="🏠 Accueil")
        st.page_link("../streamlit_app/pages/2_Connexion_Strava.py", label="🔗 Connecter Strava")

    # --- Empty / missing data states ---
    if database_url is None:
        st.warning("DATABASE_URL manquant. Ajoute-le dans les secrets Streamlit Cloud.")
        st.stop()

    if df is None or df.empty:
        st.info(
            "Aucune donnée trouvée. Connecte Strava puis relance l’ingestion / features. "
            "(Vérifie la table `activity_features`.)"
        )
        st.page_link("streamlit_app/pages/2_Connexion_Strava.py", label="➡️ Connecter Strava")
        return

    # Optional: filter by user_id if present in the dataset
    if "user_id" in df.columns:
        df_user = df[df["user_id"] == app_user_id].copy()
        if df_user.empty:
            st.info("Aucune donnée pour ton compte. Connecte Strava et relance l’ingestion.")
            st.page_link("streamlit_app/pages/2_Connexion_Strava.py", label="➡️ Connecter Strava")
            return
        df = df_user

    # --- Quick KPIs ---
    st.subheader("Résumé")
    cols = st.columns(4)
    cols[0].metric("Activités", f"{len(df):d}")

    if "start_date" in df.columns and not df["start_date"].isna().all():
        cols[1].metric("Début", str(df["start_date"].min().date()))
        cols[2].metric("Fin", str(df["start_date"].max().date()))
    else:
        cols[1].metric("Début", "—")
        cols[2].metric("Fin", "—")

    if "distance_m" in df.columns:
        cols[3].metric("Distance moy.", f"{df['distance_m'].mean() / 1000:.1f} km")
    else:
        cols[3].metric("Distance moy.", "—")

    # --- Tabs for a clearer UX ---
    tab_viz, tab_pred, tab_data = st.tabs(["📈 Visualisations", "🧠 Prédiction", "🧾 Données"])

    with tab_viz:
        st.subheader("Visualisations")

        # 1) Pace distribution
        if "pace_s_per_km" in df.columns:
            fig_pace = px.histogram(
                df,
                x="pace_s_per_km",
                nbins=25,
                title="Distribution de l'allure (sec/km)",
            )
            st.plotly_chart(fig_pace, use_container_width=True)
        else:
            st.info("Colonne `pace_s_per_km` absente : histogramme non disponible.")

        # 2) Distance vs pace
        if {"distance_m", "pace_s_per_km"}.issubset(df.columns):
            color_col = "elev_density_m_per_km" if "elev_density_m_per_km" in df.columns else None
            fig_scatter = px.scatter(
                df,
                x="distance_m",
                y="pace_s_per_km",
                color=color_col,
                labels={"distance_m": "Distance (m)", "pace_s_per_km": "Allure (sec/km)"},
                title="Distance vs allure",
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

        # 3) Timeline (if dates exist)
        if {"start_date", "pace_s_per_km"}.issubset(df.columns) and not df["start_date"].isna().all():
            fig_time = px.line(
                df.sort_values("start_date"),
                x="start_date",
                y="pace_s_per_km",
                title="Allure dans le temps",
                labels={"start_date": "Date", "pace_s_per_km": "Allure (sec/km)"},
            )
            st.plotly_chart(fig_time, use_container_width=True)

    with tab_pred:
        st.subheader("Prédiction pour la prochaine course")
        st.caption("Le modèle est entraîné sur tes activités (split temporel).")

        # Train once per session unless the user asks to retrain
        if "model" not in st.session_state or st.button("🔄 Entraîner / Mettre à jour le modèle"):
            with st.spinner("Entraînement du modèle..."):
                model, metrics = train_model(df)
            st.session_state["model"] = model
            st.session_state["metrics"] = metrics

        model = st.session_state.get("model")
        metrics = st.session_state.get("metrics")

        if model is None:
            st.warning("Le modèle ne peut pas être entraîné avec ce dataset.")
            st.stop()

        if metrics:
            st.caption(
                f"Évaluation rapide (split temporel) : MAE {metrics.get('mae', float('nan')):.1f} s/km, "
                f"RMSE {metrics.get('rmse', float('nan')):.1f} s/km"
            )

        # Athlete selection UX: preselect if single athlete
        athlete_id = None
        if "athlete_id" in df.columns and df["athlete_id"].notna().any():
            athlete_ids = sorted(df["athlete_id"].dropna().unique().tolist())
            if len(athlete_ids) == 1:
                athlete_id = athlete_ids[0]
                st.caption(f"Athlète détecté : **{athlete_id}**")
            else:
                athlete_id = st.selectbox("Athlète", athlete_ids)
        else:
            athlete_id = st.number_input("Athlete ID", min_value=0, value=0, step=1)

        with st.form("prediction_form"):
            activity_id = st.number_input("Activity ID (optionnel)", min_value=0, value=0, step=1)

            col1, col2 = st.columns(2)
            distance_km = col1.number_input("Distance de la course (km)", min_value=0.1, value=10.0)
            elevation_gain_m = col2.number_input("D+ de la course (m)", min_value=0.0, value=300.0)

            st.markdown("**Charge récente (7 jours)**")
            col3, col4, col5 = st.columns(3)
            dist_7d_km = col3.number_input("Distance 7j (km)", min_value=0.0, value=20.0)
            elev_7d_m = col4.number_input("D+ 7j (m)", min_value=0.0, value=400.0)
            time_7d_h = col5.number_input("Temps 7j (h)", min_value=0.0, value=3.0)

            st.markdown("**Charge récente (28 jours)**")
            col6, col7, col8 = st.columns(3)
            dist_28d_km = col6.number_input("Distance 28j (km)", min_value=0.0, value=80.0)
            elev_28d_m = col7.number_input("D+ 28j (m)", min_value=0.0, value=1600.0)
            time_28d_h = col8.number_input("Temps 28j (h)", min_value=0.0, value=12.0)

            submitted = st.form_submit_button("Prédire")

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
                "athlete_id": int(athlete_id) if athlete_id is not None else 0,
                "activity_id": int(activity_id) if activity_id else None,
                "prediction_type": "race_time",
                "predicted_pace_s_per_km": float(pred_pace),
                "predicted_time_s": float(pred_time),
                "features": features_df.iloc[0].to_dict(),
            }

            st.success(f"Allure estimée : {format_seconds(pred_pace)} min/km (~{pred_pace:.0f} s/km)")
            st.info(f"Temps estimé : {format_seconds(pred_time)} pour {distance_km:.1f} km")

        if database_url and "last_prediction" in st.session_state:
            st.divider()
            st.subheader("Sauvegarder la prédiction")
            st.caption("Enregistre la dernière prédiction calculée dans la table `model_predictions`.")
            if st.button("💾 Sauvegarder la dernière prédiction"):
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
                st.success("✅ Prédiction sauvegardée dans la base.")

    with tab_data:
        st.subheader("Données")
        st.caption("Aperçu du dataset utilisé pour l’analyse.")

        # Choose useful columns when available
        preferred_cols = [
            c
            for c in [
                "start_date",
                "name",
                "distance_m",
                "total_elevation_gain_m",
                "moving_time_s",
                "pace_s_per_km",
                "elev_density_m_per_km",
                "athlete_id",
            ]
            if c in df.columns
        ]

        st.dataframe(df[preferred_cols] if preferred_cols else df, use_container_width=True, height=420)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Télécharger le dataset (CSV)",
            data=csv,
            file_name="activity_features.csv",
            mime="text/csv",
        )

require_google_login()
app_user_id = ensure_app_user()

database_url = get_database_url()
df: pd.DataFrame | None = None

if database_url:
    try:
        df = _load_prepared_dataset(database_url)
    except Exception as exc:
        st.sidebar.warning(f"Erreur DB: {exc}")

render_page(df, database_url, app_user_id)
