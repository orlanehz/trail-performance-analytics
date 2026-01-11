"""Plotting helpers for trail performance analytics."""

from __future__ import annotations

import pandas as pd
import plotly.express as px


def plot_elevation_profile(df: pd.DataFrame):
    """Return a Plotly figure for elevation over index."""
    if "ele" not in df.columns:
        raise ValueError("Missing 'ele' column in dataframe")

    fig = px.line(df, y="ele", title="Profil altimetrique")
    fig.update_layout(xaxis_title="Points", yaxis_title="Elevation (m)")
    return fig
