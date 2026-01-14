from __future__ import annotations

import streamlit as st

from shared import (
    exchange_strava_code,
    fetch_strava_athlete,
    get_database_url,
    get_secret,
    ensure_app_user,
    render_profile_badge,
    render_sidebar,
    require_google_login,
    upsert_oauth_token,
)

st.title("Connecter Strava")
st.caption("Autoriser l'acces a vos activites")
render_profile_badge()

require_google_login()
app_user_id = ensure_app_user()

database_url = get_database_url()
render_sidebar(app_user_id, False)

client_id = get_secret("STRAVA_CLIENT_ID")
client_secret = get_secret("STRAVA_CLIENT_SECRET")
redirect_uri = get_secret("STRAVA_REDIRECT_URI")

st.subheader("Etapes")
st.markdown(
    """
- Cliquez sur **Autoriser Strava**
- Acceptez les permissions
- Vous revenez ici avec un `code`
"""
)

if not client_id or not client_secret or not redirect_uri:
    st.warning("Configure STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET et STRAVA_REDIRECT_URI.")
    st.stop()

if not database_url:
    st.warning("DATABASE_URL manquant. Ajoute-le dans les secrets.")
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

params = st.query_params
code = params.get("code")
error = params.get("error")
if isinstance(code, list):
    code = code[0] if code else None
if isinstance(error, list):
    error = error[0] if error else None

if error:
    st.error("Ton autorisation a ete annulee. Reessaye.")
    st.stop()

if code:
    st.success("Ok, on finalise.")
    if st.button("Finaliser"):
        token_data = exchange_strava_code(code, client_id, client_secret)
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_at = token_data.get("expires_at")
        scope = token_data.get("scope")

        if not access_token:
            st.error("Echec de l'echange de code Strava.")
            st.stop()

        athlete = fetch_strava_athlete(access_token)
        athlete_id = athlete.get("id")

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

        st.success("✅ Strava connecte")
        col1, col2 = st.columns(2)
        if col1.button("Retour a l'accueil"):
            st.switch_page("app.py")
        if col2.button("Aller au Dashboard"):
            st.switch_page("pages/1_Dashboard.py")
else:
    st.info("Apres l'autorisation Strava, vous reviendrez ici avec un `code`.")
