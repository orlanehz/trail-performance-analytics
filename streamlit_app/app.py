from __future__ import annotations

import streamlit as st

from shared import (
    ensure_app_user,
    get_database_url,
    get_db_health,
    get_dashboard_kpis,
    get_last_activity_date,
    get_last_ingestion_status,
    get_strava_token_status,
    render_sidebar,
    render_profile_badge,
)

st.set_page_config(page_title="Trail Performance Analytics", layout="wide")

st.title("Trail Performance Analytics")
st.caption("Accueil")

if not getattr(st, "user", None) or not st.user.is_logged_in:
    st.markdown("Bienvenue ! Connecte-toi pour démarrer.")
    st.button("Se connecter avec Google", on_click=st.login)
    st.stop()

app_user_id = ensure_app_user()
render_profile_badge()

# Status checks

database_url = get_database_url()
db_ok = get_db_health(database_url) if database_url else False
strava_status = get_strava_token_status(database_url, app_user_id) if db_ok else {"status": "missing"}
last_activity = get_last_activity_date(database_url) if db_ok else None
last_ingestion = get_last_ingestion_status(database_url) if db_ok else None

render_sidebar(app_user_id, strava_status.get("status") == "ok")

st.subheader("État")
col1, col2, col3 = st.columns(3)
col1.write("✅ Google connecté")
col1.write("*Étape 1/2 : Connexion Google*")

if strava_status.get("status") == "ok":
    col2.write("✅ Strava connecté")
elif strava_status.get("status") == "expired":
    col2.write("⛔ Strava expire")
else:
    col2.write("⛔ Strava non connecté")
col2.write("*Étape 2/2 : Connexion Strava*")

if last_activity:
    col3.write(f"✅ Dernière activité: {last_activity}")
elif db_ok:
    col3.write("⛔ Aucune activité importée")
else:
    col3.write("⛔ DB non disponible")

st.caption("Dernière synchronisation: " + (last_ingestion or "inconnue"))

if db_ok and strava_status.get("status") == "ok":
    kpis = get_dashboard_kpis(database_url)
    st.subheader("Derniers chiffres")
    cols = st.columns(4)
    cols[0].metric("Activites", f"{kpis['activities']}")
    cols[1].metric("Km 28j", f"{kpis['dist_28d_m'] / 1000:.1f}")
    cols[2].metric("D+ 28j", f"{kpis['elev_28d_m']:.0f}")
    if kpis["pace_avg"] is not None:
        cols[3].metric("Allure moyenne", f"{kpis['pace_avg']:.0f} s/km")
    else:
        cols[3].metric("Allure moyenne", "—")

st.subheader("Actions")
if strava_status.get("status") != "ok":
    st.caption("Étape 2/2 : Connexion Strava")
    if st.button("Connecter Strava"):
        st.switch_page("pages/5_Connexion_Strava.py")
else:
    name = getattr(st.user, "name", None)
    st.caption(f"Bonjour {name or 'athlète'} 👋")
    st.caption("Étapes complètes ✅")
    if st.button("Aller au Dashboard"):
        st.switch_page("pages/1_Dashboard.py")

st.caption("Actions secondaires")
cols = st.columns(3)
if cols[0].button("Aller à l'analyse"):
    st.switch_page("pages/2_Analyse.py")
if cols[1].button("Voir prédictions"):
    st.switch_page("pages/3_Predictions.py")
if cols[2].button("Paramètres"):
    st.switch_page("pages/4_Parametres.py")

st.divider()

st.subheader("Auto-diagnostic")
if not db_ok:
    st.warning("DB KO: vérifie DATABASE_URL et les permissions Supabase.")
    st.button("Voir logs")
if strava_status.get("status") == "expired":
    st.warning("Le token Strava est expiré. Reconnecte Strava.")
    if st.button("Reconnecter Strava"):
        st.switch_page("pages/5_Connexion_Strava.py")
if strava_status.get("status") == "missing":
    st.info("Strava non connecté.")
if db_ok and last_activity is None:
    st.warning("Aucune activité importée. Relancer l'ingestion.")
    st.button("Relancer ingestion")

st.divider()

st.subheader("À propos")
st.markdown(
    """
### À propos (Architecture)
- **Strava OAuth** → récupération des activités avec consentement
- **PostgreSQL (Supabase)** → stockage et historisation
- **Features SQL** → charge 7j/28j via fenêtres glissantes
- **Modèle ML** → Random Forest avec split temporel
- **Automatisation** → ingestion quotidienne via GitHub Actions
- **UI** → Streamlit pour connexion et dashboards

#### Secrets
Les secrets sont gérés via GitHub/Streamlit Secrets et ne sont jamais stockés dans le repo.
"""
)
