from __future__ import annotations

import streamlit as st

st.title("Compte")
st.caption("Connexion gérée par l'authentification Streamlit (Google via OIDC).")

if not getattr(st, "user", None) or not st.user.is_logged_in:
    st.info("Vous n'êtes pas connecté(e).")
    st.button("Se connecter avec Google", on_click=st.login)
    st.stop()

email = getattr(st.user, "email", None)
name = getattr(st.user, "name", None)
user_id = getattr(st.user, "id", None)

st.success("Vous êtes connecté(e) ✅")
st.write(f"**Nom :** {name or '—'}")
st.write(f"**Email :** {email or '—'}")
st.write(f"**User id :** {user_id or '—'}")

st.button("Se déconnecter", on_click=st.logout)
