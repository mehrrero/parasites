import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
import requests
import json
import geopandas as gpd
from shapely.geometry import Polygon, Point, MultiPolygon
from pyproj import Transformer


def arcgis_query_from_gdf(
    gdf_input,
    url,
    target_epsg,
    use_json_geometry=False,
    geometry_type="esriGeometryEnvelope",
    include_inSR=False
):
    """
    Query ArcGIS FeatureServer layer using a GeoDataFrame's bounding box.

    Parameters:
        gdf_input (GeoDataFrame): Any CRS
        url (str): FeatureServer query endpoint
        target_epsg (int): EPSG of target layer
        use_json_geometry (bool): Whether to send geometry as JSON object (required by some services)
        geometry_type (str): ArcGIS geometry type for envelope
        include_inSR (bool): Whether to include 'inSR' in request (e.g. for INE)

    Returns:
        GeoDataFrame in target CRS
    """

    # Transform bounds to target CRS
    if gdf_input.crs != f"EPSG:{target_epsg}":
        gdf_proj = gdf_input.to_crs(epsg=target_epsg)
    else:
        gdf_proj = gdf_input

    bounds = gdf_proj.total_bounds  # xmin, ymin, xmax, ymax
    xmin, ymin, xmax, ymax = bounds

    # Build geometry parameter
    if use_json_geometry:
        geometry = {
            "xmin": xmin,
            "ymin": ymin,
            "xmax": xmax,
            "ymax": ymax,
            "spatialReference": {"wkid": target_epsg}
        }
    else:
        geometry = f"{xmin},{ymin},{xmax},{ymax}"

    base_params = {
        "f": "json",
        "returnGeometry": "true",
        "outFields": "*",
        "outSR": target_epsg,
        "geometry": json.dumps(geometry) if use_json_geometry else geometry,
        "geometryType": geometry_type,
        "spatialRel": "esriSpatialRelIntersects",
        "where": "1=1",
        "resultRecordCount": 2000,
    }

    if include_inSR:
        base_params["inSR"] = target_epsg

    all_rows = []
    offset = 0

    while True:
        params = base_params.copy()
        params["resultOffset"] = offset

        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        features = data.get("features", [])
        if not features:
            break

        for feature in features:
            attr = feature.get("attributes", {})
            geom = feature.get("geometry")

            if not geom:
                continue

            shapely_geom = None

            if "rings" in geom:  # Polygon / MultiPolygon
                if len(geom["rings"]) == 1:
                    shapely_geom = Polygon(geom["rings"][0])
                else:
                    polys = [Polygon(shell=ring) for ring in geom["rings"]]
                    shapely_geom = MultiPolygon(polys)

            elif "x" in geom and "y" in geom:  # Point
                shapely_geom = Point(geom["x"], geom["y"])

            if shapely_geom:
                all_rows.append({**attr, "geometry": shapely_geom})

        offset += len(features)

    result_gdf = gpd.GeoDataFrame(all_rows, geometry="geometry", crs=f"EPSG:{target_epsg}")
    return result_gdf