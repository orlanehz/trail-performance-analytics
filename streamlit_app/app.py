from __future__ import annotations

import streamlit as st
from shared import require_google_login, ensure_app_user

st.set_page_config(page_title="Trail Performance Analytics", layout="wide")

require_google_login()
app_user_id = ensure_app_user()

with st.sidebar:
    st.caption(f"User ID: {app_user_id}")
    st.button("Se déconnecter", on_click=st.logout)

st.title("Trail Performance Analytics")
st.caption("Accueil de l'application Streamlit")

st.markdown(
    """
Bienvenue ! Utilise la navigation a gauche pour acceder aux pages :
- Analyse & Prediction
- Connexion Strava
- A propos
- Admin (comparaison d'athletes)
"""
)
