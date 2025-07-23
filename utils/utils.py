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


def plot_ratio_map(gdf, base_gdf, ax, ratio_col='ratio', cmap_name='Reds', n_ticks=6, title="Ratio of Airbnb Flats to Parcels per Censal Section"):
    """
    Plots a choropleth map showing the ratio column from `gdf` over a base layer `base_gdf`.

    Parameters:
        gdf (GeoDataFrame): GeoDataFrame with a `ratio_col` to plot.
        base_gdf (GeoDataFrame): Background layer for context (e.g., full censal map).
        ratio_col (str): Column in `gdf` to visualize.
        cmap_name (str): Name of matplotlib colormap.
        n_ticks (int): Number of ticks on the colorbar.
        title (str): Title of the plot.
    """

    # Get min and max of ratio
    vmin = gdf[ratio_col].min()
    vmax = gdf[ratio_col].max()

    # Define ticks and ensure max is included
    ticks = np.linspace(vmin, vmax, n_ticks)
    if not np.isclose(vmax, ticks).any():
        ticks = np.append(ticks, vmax)
    ticks = np.unique(np.round(ticks, 6))

    # Set up color normalization and colormap
    norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)
    cmap = plt.cm.get_cmap(cmap_name)
    sm = mpl.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])

    # Base layer
    base_gdf.plot(ax = ax, color='lightgrey', figsize=(10, 10))

    # Foreground: colored polygons
    gdf.plot(
        column=ratio_col,
        ax=ax,
        cmap=cmap,
        norm=norm,
        edgecolor='black',
        alpha=0.5,
        legend=False
    )

    # Custom colorbar
    cbar = plt.colorbar(sm, ax=ax, fraction=0.03, pad=0.04)
    cbar.set_label("Percentage (%)")
    cbar.set_ticks(ticks)
    cbar.set_ticklabels([f"{tick :.0f}%" for tick in ticks])

    # Increase colorbar label and tick label sizes
    cbar.ax.yaxis.label.set_size(16)
    cbar.ax.tick_params(labelsize=16)
    # Zoom to layer
    bbox = gdf.total_bounds
    ax.set_xlim(bbox[0], bbox[2])
    ax.set_ylim(bbox[1], bbox[3])

    # Formatting
    ax.set_title(title)
    ax.set_axis_off()
    plt.tight_layout()
    
    


def censal_from_gdf(input_gdf, target_wkid=102100):
    """
    Query the FeatureServer using the bounding box of a GeoDataFrame.
    
    Parameters:
    - input_gdf: GeoDataFrame with any CRS
    - target_wkid: spatial reference WKID for the query (default 102100 Web Mercator)
    
    Returns:
    - GeoDataFrame with queried features in the target CRS
    """
    # Reproject input_gdf to target CRS if necessary
    if input_gdf.crs != f"EPSG:{target_wkid}":
        gdf_proj = input_gdf.to_crs(epsg=target_wkid)
    else:
        gdf_proj = input_gdf
    
    # Extract bounding box from reprojected GeoDataFrame
    bounds = gdf_proj.total_bounds  # (xmin, ymin, xmax, ymax)
    xmin, ymin, xmax, ymax = bounds
    
    base_url = "https://www.ine.es/servergis/rest/services/Hosted/SAS_seleccion_2021/FeatureServer/6/query"
    
    geometry = {
        "xmin": xmin,
        "ymin": ymin,
        "xmax": xmax,
        "ymax": ymax,
        "spatialReference": {"wkid": target_wkid}
    }
    
    params = {
        "f": "json",
        "returnGeometry": "true",
        "spatialRel": "esriSpatialRelIntersects",
        "geometry": json.dumps(geometry),
        "geometryType": "esriGeometryEnvelope",
        "inSR": target_wkid,
        "outFields": "*",
        "outSR": target_wkid
    }
    
    response = requests.get(base_url, params=params)
    if response.status_code != 200:
        raise Exception(f"Request failed with status code {response.status_code}")
    
    data = response.json()
    
    records = []
    for feature in data.get("features", []):
        attr = feature.get("attributes", {})
        geom = feature.get("geometry", {})

        # Convert ESRI JSON geometry to shapely geometry
        if "rings" in geom:  # Polygon
            polygon = Polygon(geom["rings"][0], geom["rings"][1:] if len(geom["rings"]) > 1 else [])
            shapely_geom = polygon
        elif "x" in geom and "y" in geom:  # Point
            shapely_geom = Point(geom["x"], geom["y"])
        else:
            shapely_geom = None
        
        records.append({**attr, "geometry": shapely_geom})
    
    result_gdf = gpd.GeoDataFrame(records, geometry="geometry", crs=f"EPSG:{target_wkid}")
    return result_gdf.to_crs(input_gdf.crs)



def serpavi_from_gdf(gdf_input):
    """
    Download features from SERPAVI layer intersecting the bbox of the input GeoDataFrame.
    Returns a GeoDataFrame in EPSG:25830.
    
    Parameters:
        gdf_input (GeoDataFrame): Input GeoDataFrame, any CRS.
        
    Returns:
        GeoDataFrame with all features inside input bbox, in EPSG:25830.
    """
    # Ensure input bbox is in EPSG:4326 for transforming
    gdf_wgs84 = gdf_input.to_crs("EPSG:4326")
    bounds = gdf_wgs84.total_bounds  # (xmin, ymin, xmax, ymax)

    # Transform bbox to EPSG:25830
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:25830", always_xy=True)
    xmin_25830, ymin_25830 = transformer.transform(bounds[0], bounds[1])
    xmax_25830, ymax_25830 = transformer.transform(bounds[2], bounds[3])

    url = "https://services1.arcgis.com/nCKYwcSONQTkPA4K/ArcGIS/rest/services/Sistema_Estatal_de_Referencia_del_Precio_del_Alquiler_de_Vivienda_Solo_lectura/FeatureServer/0/query"

    base_params = {
        "f": "json",
        "returnGeometry": "true",
        "outFields": "*",
        "outSR": 25830,
        "geometry": f"{xmin_25830},{ymin_25830},{xmax_25830},{ymax_25830}",
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "where": "1=1",
        "resultRecordCount": 2000,
    }

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
            geom = feature.get("geometry")
            if not geom:
                continue

            rings = geom.get("rings")
            if not rings:
                continue

            if len(rings) == 1:
                polygon = Polygon(shell=rings[0])
            else:
                polys = [Polygon(shell=ring) for ring in rings]
                polygon = MultiPolygon(polys)

            props = feature.get("attributes", {})
            all_rows.append({**props, "geometry": polygon})

        offset += len(features)

    result_gdf = gpd.GeoDataFrame(all_rows, crs="EPSG:25830")
    return result_gdf


