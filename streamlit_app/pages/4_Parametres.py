from __future__ import annotations

import streamlit as st

from shared import (
    ensure_app_user,
    get_database_url,
    get_strava_token_status,
    render_profile_badge,
    render_sidebar,
    require_google_login,
)


require_google_login()
app_user_id = ensure_app_user()

render_profile_badge()

database_url = get_database_url()
strava_status = get_strava_token_status(database_url, app_user_id) if database_url else {"status": "missing"}

render_sidebar(app_user_id, strava_status.get("status") == "ok")

st.title("Parametres")
st.caption("Compte et connexions")

st.subheader("Compte Google")
email = getattr(st.user, "email", None)
name = getattr(st.user, "name", None)
st.write(f"**Nom :** {name or '—'}")
st.write(f"**Email :** {email or '—'}")

st.subheader("Strava")
if strava_status.get("status") == "ok":
    st.success("Strava connecte")
elif strava_status.get("status") == "expired":
    st.warning("Token Strava expire")
else:
    st.info("Strava non connecte")

if st.button("Reconnecter Strava"):
    st.switch_page("pages/5_Connexion_Strava.py")

st.subheader("Session")
st.button("Se deconnecter", on_click=st.logout)
