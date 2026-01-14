from __future__ import annotations

import time

import streamlit as st

from shared import (
    exchange_google_code,
    fetch_google_profile,
    get_database_url,
    get_secret,
    upsert_app_user,
    upsert_oauth_token,
)

st.title("Connexion Google")
st.caption("Autoriser l'acces via Google OAuth")

client_id = get_secret("GOOGLE_CLIENT_ID")
client_secret = get_secret("GOOGLE_CLIENT_SECRET")
redirect_uri = get_secret("GOOGLE_REDIRECT_URI")
database_url = get_database_url()

st.subheader("Etapes")
st.markdown(
    """
1. Cliquez sur "Autoriser Google"
2. Acceptez les permissions
3. Vous serez redirige avec un parametre `code`
4. Cliquez sur "Finaliser la connexion" pour enregistrer l'utilisateur
"""
)

if not client_id or not client_secret or not redirect_uri:
    st.warning("Configure GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET et GOOGLE_REDIRECT_URI.")
    st.stop()

auth_url = (
    "https://accounts.google.com/o/oauth2/v2/auth"
    f"?client_id={client_id}"
    "&response_type=code"
    f"&redirect_uri={redirect_uri}"
    "&scope=openid%20email%20profile"
    "&access_type=offline"
    "&prompt=consent"
)
st.link_button("Autoriser Google", auth_url)

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

        token_data = exchange_google_code(code, client_id, client_secret, redirect_uri)
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in")

        if not access_token:
            st.error("Echec de l'echange de code.")
            st.stop()

        profile = fetch_google_profile(access_token)
        provider_user_id = str(profile.get("id"))
        email = profile.get("email")
        name = profile.get("name")

        user_id = upsert_app_user(
            database_url=database_url,
            provider="google",
            provider_user_id=provider_user_id,
            email=email,
            name=name,
            raw=profile,
        )

        expires_at = None
        if expires_in:
            expires_at = int(time.time()) + int(expires_in)

        upsert_oauth_token(
            database_url=database_url,
            user_id=user_id,
            provider="google",
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            scope=token_data.get("scope"),
            raw=token_data,
        )

        st.success("Connexion Google terminee. Utilisateur enregistre.")
else:
    st.info("Apres l'autorisation, vous reviendrez ici avec un `code`.")
