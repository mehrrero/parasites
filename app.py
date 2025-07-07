import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import folium_static
import numpy as np
from utils import count_houses, plot_ratio_map
import matplotlib.pyplot as plt

# Data preprocessing

censal = gpd.read_file('data/censal_sections.geojson')
barris = gpd.read_file('data/barris.geojson')
districts = gpd.read_file('data/districts.geojson')
edges = gpd.read_file('data/edges.geojson')

st.title("Interactive Choropleth Map")

# Division selection
division = st.selectbox("Select a division", options=["Districts", "Barris", "Censal Sections"])
# Division selection
type = st.selectbox("Select a type of rental", options=["All", "Full apparment", "Rooms"])

if division == "Districts":
    gdf = districts
    st.write("Districts of Barcelona")
elif division == "Barris":
    gdf = barris
    st.write("Barris of Barcelona")
else:
    gdf = censal
    st.write("Censal Sections of Barcelona")

if type == "Full apparment":
    col = 'ratio_flats'
elif type == "Rooms":
    col = 'ratio_rooms'
elif type == "All":
    col = 'ratio'


# Ensure unique index for matching
gdf = gdf.reset_index(drop=True)
gdf.index.name = 'id'  # Choropleth will use this as feature.id

# Create Folium map
m = folium.Map(
    location=[41.3874, 2.1686],
    zoom_start=12,
    tiles='CartoDB positron'
)

# Add choropleth
folium.Choropleth(
    geo_data=gdf,
    data=gdf,
    columns=[gdf.index, col],
    key_on='feature.id',
    fill_color='YlOrRd',
    fill_opacity=0.7,
    line_opacity=0.2,
    legend_name='Percentage of Airbnb Flats',
    highlight=True,
).add_to(m)

folium.GeoJson(
    gdf,
    tooltip=folium.GeoJsonTooltip(fields=[col], aliases=["Ratio:"]),
    style_function=lambda feature: {
        'fillOpacity': 0,
        'color': 'transparent'
    }
).add_to(m)

# Show map in Streamlit
folium_static(m)

# Filter hotspots
hottest = censal[censal[col] > 5]
# Create figure
fig, ax = plt.subplots(figsize=(10, 10))
# Plot background edges
edges.plot(ax=ax, alpha=0.4, color='grey')
# Your custom function (assuming this exists)
plot_ratio_map(hottest, censal, ax, ratio_col=col)
# Annotate places
annotations = [
        (2.1742309820379906, 41.403593049470885, "Sagrada Familia"),
        (2.169841171395862, 41.38688665835762, "Plaça Catalunya"),
        (2.189651884769526, 41.379463437793035, "La Barceloneta"),
        (2.1573058193393004, 41.36641505140188, "Montjuïc")
    ]
for x, y, name in annotations:
    ax.text(x, y, name, fontsize=8, fontweight='bold', color='black', ha='center', va='center')


# Show the plot in Streamlit
st.pyplot(fig)