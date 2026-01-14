from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Trail Performance Analytics", layout="wide")

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
