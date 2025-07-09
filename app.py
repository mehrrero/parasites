import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import folium_static
import numpy as np
from utils.utils import count_houses, plot_ratio_map
import matplotlib.pyplot as plt



st.set_page_config(
    page_title="Airbnb in Barcelona",
    page_icon="🏠",
    layout="wide",
)

# Data preprocessing

censal = gpd.read_file('data/censal_sections.geojson')
barris = gpd.read_file('data/barris.geojson')
districts = gpd.read_file('data/districts.geojson')
edges = gpd.read_file('data/edges.geojson')

st.title("Percentage of Airbnb's in Barcelona")
st.text("You can select different divisions and types of Airbnb rentals to explore the data and see how much housing"
         " is devoted to Airbnb in different areas of the city."
         )
# Division selection
division = st.selectbox("Select a division", options=["Censal Sections", "Neighborhoods", "Districts"])
# Type selection
type = st.selectbox("Select a type of Airbnb rental", options=["All", "Full aparments", "Rooms"])

if division == "Districts":
    gdf = districts
    st.write("Districts of Barcelona")
elif division == "Neighborhoods":
    gdf = barris
    st.write("Neighborhoods of Barcelona")
else:
    gdf = censal
    st.write("Censal Sections of Barcelona")

if type == "Full aparments":
    col = 'ratio_flats'
elif type == "Rooms":
    col = 'ratio_rooms'
elif type == "All":
    col = 'ratio'


# Ensure unique index for matching
gdf = gdf.reset_index(drop=True)
gdf.index.name = 'id'  # Choropleth will use this as feature.id
gdf[col] = gdf[col].astype(float).round(1) # Ensure the column is float and rounded to 1 decimal place




# Create Folium map
m = folium.Map(
    location=[41.3874, 2.1686],
    zoom_start=13,
    tiles='CartoDB positron'
)


# Add choropleth
folium.Choropleth(
    geo_data=gdf,
    data=gdf,
    columns=[gdf.index, col],
    key_on='feature.id',
    fill_color='Reds',
    fill_opacity=0.7,
    line_opacity=0.2,
    legend_name='Percentage of Airbnb',
    highlight=True,
).add_to(m)

folium.GeoJson(
    gdf,
    tooltip=folium.GeoJsonTooltip(fields=[col], aliases=["%:"]),
    style_function=lambda feature: {
        'fillOpacity': 0,
        'color': 'transparent'
    }
).add_to(m) # Add GeoJson for tooltips

# Prepare top 30 censal sections by ratio
top_censals = censal.sort_values(col, ascending=False).head(30)
# Format x-axis labels as percentages
# Create the plot
fig, ax = plt.subplots(figsize=(10, 10))
# Set font sizes for title and axis labels
title_fontsize = 20
label_fontsize = 16
# Increase font size for labels
ax.tick_params(axis='y', labelsize=label_fontsize)
ax.tick_params(axis='x', labelsize=label_fontsize)
# Horizontal bar plot
ax.barh(top_censals['NOM'], top_censals[col], color=plt.cm.Reds(top_censals[col] / top_censals[col].max()))

# Labels and title
ax.set_title("Top 30 Censal Sections by %", fontsize=title_fontsize)
ax.set_xlabel(f"Percentage of {type}", fontsize=label_fontsize)
ax.set_ylabel("Neighborhood", fontsize=label_fontsize)
ax.set_xticklabels([f"{x:.0f}%" for x in ax.get_xticks()])
# Invert y-axis to show the highest ratio on top
ax.invert_yaxis()




col1, col2 = st.columns(2)

with col1:
    folium_static(m, width=600, height=500)

with col2:
    st.pyplot(fig)
 
# Filter hotspots
hottest = censal[censal[col] > 5]
# Create figure
fig_map, ax_map = plt.subplots(figsize=(10, 10))
# Plot background edges
edges.plot(ax=ax_map, alpha=0.4, color='grey')
# Plot the values
plot_ratio_map(hottest, censal, ax_map, ratio_col=col)

ax_map.set_title("A closer look at the most problematic areas", fontsize=title_fontsize)
ax_map.set_xlabel("Percentage", fontsize=label_fontsize)
ax_map.set_ylabel("Censal Section", fontsize=label_fontsize)
ax_map.tick_params(axis='y', labelsize=label_fontsize)
ax_map.tick_params(axis='x', labelsize=label_fontsize)

# Annotate places
annotations = [
        (2.1742309820379906, 41.403593049470885, "Sagrada Familia"),
        (2.169841171395862, 41.38688665835762, "Plaça Catalunya"),
        (2.188651884769526, 41.379463437793035, "La Barceloneta"),
        (2.1633058193393004, 41.36641505140188, "Montjuïc")
    ]
for x, y, name in annotations:
    ax_map.text(
        x, y, name,
        fontsize=16,
        fontweight='bold',
        color='black',
        ha='center',
        va='center',
        bbox=dict(
            facecolor='white',   # Background color
            edgecolor='none',    # No border
            boxstyle='round,pad=0.3',  # Rounded box with padding
            alpha=0.6           # Slight transparency (optional)
        )
    )



# Show the plot in Streamlit
st.write("")
st.write("")
st.write("")
st.write("")
col1, col2 = st.columns(2)

with col1:
    st.pyplot(fig_map)

with col2:
    st.write("")
    st.write("")
    st.text("We can get a deeper insight into those zones of Barcelona with a higher percentage of airbnbs by zooming in the map and focusing only "
                "on those censal sections with a percentage higher than 5%, where we have overimposed the street network of Barcelona for better visualization."
                "\n\nNote how some cultural landmarks like the Sagrada Familia, Plaça Catalunya, La Barceloneta, and Montjuïc are hotspots for Airbnb rentals."
                " This is a clear indication of the impact of tourism in these areas, which are often the most attractive for visitors."
                " This map can be used to identify areas where the concentration of Airbnb rentals is particularly high, "
                "which can help in understanding the dynamics of tourism and housing in Barcelona."
                "\n\nThose areas with a high concentration of Airbnb rentals can be considered as 'parasites' in the sense that they are taking away apartments from local residents,"
                " leading to a decrease in the availability of affordable housing for locals." )

st.markdown("### Methodology:\n\nThese results have been generated by counting the number of Airbnb rentals in each censal section and dividing it by the total number of houses/apartments in that section."
        " All data is open access. Housing data can be obtained from the [Spanish cadaster Inspire system](https://www.catastro.hacienda.gob.es/webinspire/index.html),"
        " while Airbnb data is available through the [Inside Airbnb project](http://insideairbnb.com/get-the-data.html). The dataset used here includes all "
        "Airbnb listings in Barcelona in the period January-March 2025. The street network was obtained from [OpenStreetMap](https://www.openstreetmap.org/]) using the [OSMnx library](https://osmnx.readthedocs.io/)."
        "\n\nAll code is available on [GitHub](https://github.com/mehrrero/parasites) and has been developed by [**Míriam Herrero, PhD**](https://www.linkedin.com/in/m-herrero-valea/)."
        )