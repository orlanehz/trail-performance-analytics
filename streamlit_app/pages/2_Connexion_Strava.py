from __future__ import annotations

import streamlit as st

from shared import (
    exchange_strava_code,
    fetch_strava_athlete,
    get_database_url,
    get_secret,
    ensure_app_user,
    require_google_login,
    upsert_oauth_token,
)


st.title("Connecter Strava")
st.caption("Autoriser l'accès à vos activités Strava (OAuth)")

# 1) Require Google login first (user identity)
require_google_login()

# 2) Load Strava secrets
client_id = get_secret("STRAVA_CLIENT_ID")
client_secret = get_secret("STRAVA_CLIENT_SECRET")
redirect_uri = get_secret("STRAVA_REDIRECT_URI")
database_url = get_database_url()

st.info(
    "Vous êtes connecté(e) via Google en tant que : "
    f"**{getattr(st.user, 'email', 'email inconnu')}**"
)

st.subheader("Étapes")
st.markdown(
    """
1. Cliquez sur **Autoriser Strava**
2. Acceptez les permissions
3. Vous serez redirigé(e) ici avec un paramètre `code`
4. Cliquez sur **Finaliser la connexion** pour enregistrer le token Strava
"""
)

if not client_id or not client_secret or not redirect_uri:
    st.warning("Configure STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET et STRAVA_REDIRECT_URI.")
    st.stop()

# Build Strava authorize URL
auth_url = (
    "https://www.strava.com/oauth/authorize"
    f"?client_id={client_id}"
    "&response_type=code"
    f"&redirect_uri={redirect_uri}"
    "&approval_prompt=force"
    "&scope=read,activity:read_all"
)

st.link_button("Autoriser Strava", auth_url)

# Read OAuth callback params
params = st.query_params
code = params.get("code")
error = params.get("error")
if isinstance(code, list):
    code = code[0] if code else None
if isinstance(error, list):
    error = error[0] if error else None

if error:
    st.error(f"Erreur OAuth Strava: {error}")
    st.stop()

# If we got a code, allow the user to finalize
if code:
    st.success("Code reçu. Vous pouvez finaliser la connexion Strava.")

    if st.button("Finaliser la connexion"):
        if not database_url:
            st.error("DATABASE_URL manquant. Ajoute-le dans les secrets.")
            st.stop()

        app_user_id = ensure_app_user()

        # --- Exchange the Strava code for tokens ---
        token_data = exchange_strava_code(code, client_id, client_secret)
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_at = token_data.get("expires_at")
        scope = token_data.get("scope")

        if not access_token:
            st.error("Échec de l'échange de code Strava.")
            st.stop()

        # Optional: fetch athlete profile for traceability/debug
        athlete = fetch_strava_athlete(access_token)
        athlete_id = athlete.get("id")

        # --- Store Strava tokens linked to the Google app_user ---
        upsert_oauth_token(
            database_url=database_url,
            user_id=app_user_id,
            provider="strava",
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=int(expires_at) if expires_at else None,
            scope=scope,
            raw={
                **(token_data or {}),
                "athlete": athlete,
                "athlete_id": athlete_id,
            },
        )

        st.success("✅ Strava connecté ! Vos tokens sont associés à votre compte Google.")
        st.caption("Vous pouvez maintenant revenir aux pages d'analyse.")
else:
    st.info("Après l'autorisation Strava, vous reviendrez ici avec un paramètre `code`.")
