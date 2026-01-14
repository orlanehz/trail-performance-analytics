from __future__ import annotations

import streamlit as st

from shared import (
    exchange_strava_code,
    fetch_strava_athlete,
    get_database_url,
    get_secret,
    upsert_app_user,
    upsert_oauth_token,
)

st.title("Connexion Strava")
st.caption("Autoriser l'acces a vos activites via OAuth")

client_id = get_secret("STRAVA_CLIENT_ID")
client_secret = get_secret("STRAVA_CLIENT_SECRET")
redirect_uri = get_secret("STRAVA_REDIRECT_URI")
database_url = get_database_url()

st.subheader("Etapes")
st.markdown(
    """
1. Cliquez sur "Autoriser Strava"
2. Acceptez les permissions
3. Vous serez redirige avec un parametre `code`
4. Cliquez sur "Finaliser la connexion" pour enregistrer l'utilisateur
"""
)

if not client_id or not client_secret or not redirect_uri:
    st.warning("Configure STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET et STRAVA_REDIRECT_URI.")
    st.stop()

auth_url = (
    "https://www.strava.com/oauth/authorize"
    f"?client_id={client_id}"
    "&response_type=code"
    f"&redirect_uri={redirect_uri}"
    "&approval_prompt=force"
    "&scope=read,activity:read_all"
)
st.link_button("Autoriser Strava", auth_url)

params = st.query_params
code = params.get("code")
error = params.get("error")
if isinstance(code, list):
    code = code[0] if code else None
if isinstance(error, list):
    error = error[0] if error else None

if error:
    st.error(f"Erreur OAuth: {error}")
    st.stop()

if code:
    st.success("Code recu. Vous pouvez finaliser la connexion.")
    if st.button("Finaliser la connexion"):
        if not database_url:
            st.error("DATABASE_URL manquant. Ajoute-le dans les secrets.")
            st.stop()

        token_data = exchange_strava_code(code, client_id, client_secret)
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_at = token_data.get("expires_at")
        scope = token_data.get("scope")

        if not access_token:
            st.error("Echec de l'echange de code.")
            st.stop()

        athlete = fetch_strava_athlete(access_token)
        athlete_id = str(athlete.get("id"))
        name = f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip() or None

        user_id = upsert_app_user(
            database_url=database_url,
            provider="strava",
            provider_user_id=athlete_id,
            email=None,
            name=name,
            raw=athlete,
        )

        upsert_oauth_token(
            database_url=database_url,
            user_id=user_id,
            provider="strava",
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=int(expires_at) if expires_at else None,
            scope=scope,
            raw=token_data,
        )

        st.success("Connexion Strava terminee. Utilisateur enregistre.")
else:
    st.info("Apres l'autorisation, vous reviendrez ici avec un `code`.")
