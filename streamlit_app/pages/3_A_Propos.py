from __future__ import annotations

import streamlit as st

st.title("A propos")
st.caption("Architecture et principes de securite")

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
