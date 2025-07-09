import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np



def count_houses(parcels: gpd.GeoDataFrame, 
                                 censal: gpd.GeoDataFrame,
                                 out_label: str , 
                                 parcel_id_col: str = 'parcel_id', 
                                 apartments_col: str = None) -> gpd.GeoDataFrame:
    """
    Counts total number of apartments (or parcels, if apartments_col is None)
    intersecting each censal section.

    Parameters:
    - parcels: GeoDataFrame with parcel geometries.
    - censal: GeoDataFrame with censal section geometries.
    - parcel_id_col: Column name to use as a unique parcel ID (defaults to 'parcel_id').
    - apartments_col: Column with apartment counts per parcel. If None, each parcel counts as 1 apartment.

    Returns:
    - censal GeoDataFrame with added 'n_apartments' column.
    """
    
    # Add a unique ID if not present
    if parcel_id_col not in parcels.columns:
        parcels[parcel_id_col] = parcels.index

    # If no apartments_col is given, create a temporary one with all 1s
    temp_col = False
    if apartments_col is None:
        apartments_col = '_tmp_apartment_count'
        parcels[apartments_col] = 1
        temp_col = True
    else:
        # Ensure apartment counts are numeric
        parcels[apartments_col] = pd.to_numeric(parcels[apartments_col], errors='coerce').fillna(0)

    # Perform spatial join
    joined = gpd.sjoin(parcels, censal, how='inner', predicate='intersects')

    # Drop duplicates to ensure each parcel is counted once
    joined_unique = joined.drop_duplicates(subset=parcel_id_col)

    # Sum apartments per censal section
    apartments_per_censal = joined_unique.groupby('index_right')[apartments_col].sum()

    # Add result to censal GeoDataFrame
    censal = censal.copy()
    censal[out_label] = censal.index.map(apartments_per_censal).fillna(0).astype(int)

    # Clean up temporary column if created
    if temp_col:
        parcels.drop(columns=[apartments_col], inplace=True)

    return censal



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
    
    
