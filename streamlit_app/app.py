from __future__ import annotations

import streamlit as st

from shared import ensure_app_user, get_database_url, has_oauth_token, render_profile_badge, require_google_login

st.set_page_config(page_title="Trail Performance Analytics", layout="wide")

# 1) Arrive -> Google login
require_google_login()
app_user_id = ensure_app_user()

render_profile_badge()

with st.sidebar:
    st.caption(f"User ID: {app_user_id}")
    st.button("Se deconnecter", on_click=st.logout)

st.title("Trail Performance Analytics")
st.caption("Accueil")

database_url = get_database_url()
strava_connected = False
if database_url:
    strava_connected = has_oauth_token(database_url, app_user_id, "strava")

st.subheader("Connexions")
col1, col2 = st.columns(2)
col1.write("✅ Google connecte")
col2.write("✅ Strava connecte" if strava_connected else "❌ Strava non connecte")

st.subheader("Actions")
if not strava_connected:
    if st.button("Connecter Strava"):
        st.switch_page("pages/2_Connexion_Strava.py")
else:
    st.success("Strava est connecte. Tu peux acceder a l'analyse.")

if st.button("Aller a l'analyse", disabled=not strava_connected):
    st.switch_page("pages/1_Analyse.py")

st.divider()
st.subheader("A propos")
st.markdown(
    """
### A propos (Architecture)
- **Strava OAuth** → recuperation des activites avec consentement
- **PostgreSQL (Supabase)** → stockage et historisation
- **Features SQL** → charge 7j/28j via fenetres glissantes
- **Modele ML** → Random Forest avec split temporel
- **Automatisation** → ingestion quotidienne via GitHub Actions
- **UI** → Streamlit pour connexion et dashboards

#### Secrets
Les secrets sont geres via GitHub/Streamlit Secrets et ne sont jamais stockes dans le repo.
"""
)
