import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from utils.utils import count_houses, plot_ratio_map
import osmnx as ox
from catastro.atom import ATOM_Query
import os
import json
import requests
import gzip
import shutil
import zipfile
import io

# Load rental houses categories from JSON file
with open('data/houses_categories.json', 'r') as f_read:
    rental_houses = json.load(f_read)

def format_location_path(location_str):
    parts = location_str.lower().replace(" ", "").split(",")
    return "/".join(reversed(parts))

class city:
    def __init__(self, name, province, insideabnb_handle, date):
        self.name = name
        self.province = province
        self.insideabnb_handle = insideabnb_handle
        self.date = date


    def get_parcels(self):
        query = ATOM_Query(self.name, self.province)
        parcels = query.download_gml()
        parcels.to_crs("EPSG:4326", inplace=True)
        parcels.rename(columns={
            'parcel_id': 'id',
        }, inplace=True)
        self.parcels = parcels
        print(f"Downloaded parcels for {self.name} in {self.province}.")
        
    def get_airbnb_data(self):
        baseurl = "https://data.insideairbnb.com/"
        # Format the URL based on the insideabnb_handle
        url = baseurl + format_location_path(self.insideabnb_handle) + "/" + self.date +"/data/listings.csv.gz"
        compressed_path = f"data/cache/{self.name}/listings.csv.gz"
        decompressed_path = f"data/cache/{self.name}/listings.csv"

        os.makedirs(f"data/cache/{self.name}", exist_ok=True)

        # Check if decompressed file already exists
        if os.path.exists(decompressed_path):
            print(f"Using cached Airbnb data from {decompressed_path}")
        else:
            # Check if compressed file exists
            if not os.path.exists(compressed_path):
                print("Downloading Airbnb data...")
                response = requests.get(url, stream=True)
                response.raise_for_status()
                with open(compressed_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
            else:
                print(f"Using cached compressed file at {compressed_path}")

            # Decompress the file
            print("Decompressing data...")
            with gzip.open(compressed_path, "rb") as f_in:
                with open(decompressed_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            print(f"Decompressed Airbnb data to {decompressed_path}")

        # Load the CSV into a DataFrame
        listings = pd.read_csv(decompressed_path)
        listings['geometry'] = gpd.points_from_xy(listings['longitude'], listings['latitude'])
        listings = gpd.GeoDataFrame(listings, geometry='geometry', crs="EPSG:4326")
        listings['property_type_basic'] = listings['property_type'].apply(lambda x: 'Flat' if x in rental_houses else 'Room')
        self.listings = listings
        self.flats = listings[listings['property_type_basic'] == 'Flat']
        self.rooms = listings[listings['property_type_basic'] == 'Room']

    def get_censal_sections(self):
        url = "https://www.ine.es/prodyser/cartografia/seccionado_2025.zip"
        shp_dir = "data/cache/seccionado_2025"
        
        if any(fname.endswith('.shp') for fname in os.listdir(shp_dir + "/España_Seccionado2025_ETRS89H30")) if os.path.exists(shp_dir) else False:
            print("Shapefile already exists in data/seccionado_2025, skipping download.")
            
        else: 
            print("Downloading censal sections data...")
            os.makedirs(shp_dir, exist_ok=True)
            response = requests.get(url)
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                z.extractall("data/cache/seccionado_2025")
                
        censal = gpd.read_file('data/cache/seccionado_2025/España_Seccionado2025_ETRS89H30/SECC_CE_20250101.shp').to_crs('EPSG:4326')
        censal = censal[censal['NMUN'] == self.name.capitalize()]
        self.censal_sections = censal


    def count_houses(self, gdf, out_label, apartments_col=None):
        """
        Counts total number of apartments (or parcels, if apartments_col is None)
        intersecting each censal section.

        Parameters:
        - gdf: GeoDataFrame with geometries.
        - out_label: Column name to store the count result.
        - parcel_id_col: Column name to use as a unique parcel ID (defaults to 'parcel_id').
        - apartments_col: Column with apartment counts per parcel. If None, each parcel counts as 1 apartment.

        Returns:
        - GeoDataFrame with added out_label column.
        """
        return count_houses(gdf, self.censal_sections, out_label, apartments_col)[['geometry', out_label]]
    
    def compute_ratios(self):
        """
        Computes the ratio of flats and rooms to parcels in the censal sections.
        """
        out_b = self.count_houses(self.parcels, out_label='n_parcels', apartments_col='numberOfDwellings')
        out_f = self.count_houses(self.flats, out_label='n_flats', apartments_col=None)
        out_r = self.count_houses(self.rooms, out_label='n_rooms', apartments_col=None)

        # Merge results
        out = out_b.merge(out_f, on='geometry', how='outer')
        out = out.merge(out_r, on='geometry', how='outer')
        out['n_all'] = out['n_rooms'] + out['n_flats']
        out = out[out['n_parcels'] > 0]

        # Calculate ratios
        out['ratio_flats'] = 100 * out['n_flats'] / out['n_parcels']
        out['ratio_rooms'] = 100 * out['n_rooms'] / out['n_parcels']
        out['ratio'] = 100 * (out['n_flats'] + out['n_rooms']) / out['n_parcels']

        self.results = out


    def get_results(self, save_path=None):
        self.get_parcels()
        self.get_airbnb_data()
        self.get_censal_sections()
        self.compute_ratios()
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            self.results.to_file(save_path, driver='GeoJSON')
        print("Computed ratios for flats and rooms in the city.")
        
    def get_edges(self, save_path=None):
        """
        Downloads the street network for the city and saves it as a GeoJSON file.
        """
        bbox = self.results.total_bounds
        G = ox.graph_from_bbox(bbox, network_type="walk", simplify=True, retain_all=True, truncate_by_edge=False)
        self.edges = ox.graph_to_gdfs(G, nodes=False)
        print(f"Downloaded street network for {self.name}.")
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            self.edges.to_file(save_path, driver='GeoJSON')
       
##################################
##################################


if __name__ == "__main__":
    # Create a city instance for Barcelona
    bcn = city("barcelona","Barcelona","Barcelona, Catalonia, Spain", "2025-06-12")
    bcn.get_results('data/results/barcelona.geojson')
    