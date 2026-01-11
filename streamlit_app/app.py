import streamlit as st

from src.config import get_settings
from src.importer import load_gpx, load_tcx
from src.visualisation.plots import plot_elevation_profile


st.set_page_config(page_title="Trail Performance Analytics", layout="wide")

settings = get_settings()

st.title("Trail Performance Analytics")
st.caption("Analyse rapide de traces GPX/TCX")

uploaded = st.file_uploader("Choisir un fichier GPX ou TCX", type=["gpx", "tcx"])

if uploaded:
    suffix = uploaded.name.lower().split(".")[-1]
    if suffix == "gpx":
        df = load_gpx(uploaded)
    elif suffix == "tcx":
        df = load_tcx(uploaded)
    else:
        st.error("Format non pris en charge")
        st.stop()

    st.subheader("Apercu")
    st.dataframe(df.head(50), use_container_width=True)

    if "ele" in df.columns and df["ele"].notna().any():
        st.subheader("Profil altimetrique")
        fig = plot_elevation_profile(df)
        st.plotly_chart(fig, use_container_width=True)

st.sidebar.header("Configuration")
st.sidebar.write(
    {
        "data_dir": settings.data_dir,
        "strava_client_id": settings.strava_client_id,
        "garmin_api_key": settings.garmin_api_key,
    }
)
