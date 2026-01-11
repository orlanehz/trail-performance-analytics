"""Utilities to import GPX/TCX files into Pandas dataframes."""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd


def load_gpx(path: str | Path) -> pd.DataFrame:
    """Load a GPX file and return a normalized dataframe.

    Extracts time, latitude, longitude and elevation from track points.
    """
    tree = ET.parse(Path(path))
    root = tree.getroot()
    ns = {"gpx": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}

    rows = []
    for trkpt in root.findall(".//gpx:trkpt", ns) if ns else root.findall(".//trkpt"):
        lat = trkpt.attrib.get("lat")
        lon = trkpt.attrib.get("lon")
        ele_elem = trkpt.find("gpx:ele", ns) if ns else trkpt.find("ele")
        time_elem = trkpt.find("gpx:time", ns) if ns else trkpt.find("time")
        rows.append(
            {
                "time": time_elem.text if time_elem is not None else None,
                "lat": float(lat) if lat else None,
                "lon": float(lon) if lon else None,
                "ele": float(ele_elem.text) if ele_elem is not None else None,
            }
        )

    return pd.DataFrame(rows)


def load_tcx(path: str | Path) -> pd.DataFrame:
    """Load a TCX file and return a normalized dataframe.

    Extracts time, latitude, longitude and elevation from track points.
    """
    tree = ET.parse(Path(path))
    root = tree.getroot()
    ns = {"tcx": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}

    rows = []
    trackpoints = root.findall(".//tcx:Trackpoint", ns) if ns else root.findall(".//Trackpoint")
    for tp in trackpoints:
        time_elem = tp.find("tcx:Time", ns) if ns else tp.find("Time")
        pos_elem = tp.find("tcx:Position", ns) if ns else tp.find("Position")
        lat_elem = pos_elem.find("tcx:LatitudeDegrees", ns) if pos_elem is not None and ns else (
            pos_elem.find("LatitudeDegrees") if pos_elem is not None else None
        )
        lon_elem = pos_elem.find("tcx:LongitudeDegrees", ns) if pos_elem is not None and ns else (
            pos_elem.find("LongitudeDegrees") if pos_elem is not None else None
        )
        ele_elem = tp.find("tcx:AltitudeMeters", ns) if ns else tp.find("AltitudeMeters")

        rows.append(
            {
                "time": time_elem.text if time_elem is not None else None,
                "lat": float(lat_elem.text) if lat_elem is not None else None,
                "lon": float(lon_elem.text) if lon_elem is not None else None,
                "ele": float(ele_elem.text) if ele_elem is not None else None,
            }
        )

    return pd.DataFrame(rows)
