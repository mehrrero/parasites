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

# Load rental houses categories from JSON file
with open('data/houses_categories.json', 'r') as f_read:
    rental_houses = json.load(f_read)

def format_location_path(location_str):
    parts = location_str.lower().replace(" ", "").split(",")
    return "/".join(reversed(parts))

class city:
    def __init__(self, name, province, insideabnb_handle):
        self.name = name
        self.province = province
        self.insideabnb_handle = insideabnb_handle


    def get_parcels(self):
        query = ATOM_Query(self.name, self.province)
        parcels = query.download_gml()
        parcels.to_crs("EPSG:4326", inplace=True)
        self.parcels = parcels
        print(f"Downloaded parcels for {self.name} in {self.province}.")
        
    def get_airbnb_data(self):
        baseurl = "https://data.insideairbnb.com/"
        # Format the URL based on the insideabnb_handle
        url = baseurl + format_location_path(self.insideabnb_handle) + "/data/listings.csv.gz"
        compressed_path = f"data/{self.name}/listings.csv.gz"
        decompressed_path = f"data/{self.name}/listings.csv"

        os.makedirs("data", exist_ok=True)

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
        self.listings = pd.read_csv(decompressed_path)





##################################
##################################


if __name__ == "__main__":
    query = ATOM_Query('Barcelona', 'Barcelona')
    parcels = query.download_gml()
    parcels.to_crs("EPSG:4326", inplace=True)
    
    if not os.path.exists("data/barcelona.csv"):
        raise FileNotFoundError("The file 'data/barcelona.csv' does not exist. Please download it from Inside Airbnb and place it in the 'data' directory.")
        
    bcn = pd.read_csv("data/barcelona.csv") #This needs to be downloaded from Inside Airbnb
    bcn['geometry'] = gpd.points_from_xy(bcn['longitude'], bcn['latitude'])
    bcn = gpd.GeoDataFrame(bcn, geometry='geometry', crs="EPSG:4326")
    bcn['property_type_basic'] = bcn['property_type'].apply(lambda x: 'Flat' if x in rental_houses else 'Room')
    flats = bcn[bcn['property_type_basic'] == 'Flat']
    rooms = bcn[bcn['property_type_basic'] == 'Room']
    ad_boundaries = gpd.read_file('data/0301100100_UNITATS_ADM_POLIGONS.json')
    ad_boundaries = ad_boundaries.to_crs('EPSG:4326')
    censal = ad_boundaries[ad_boundaries['SCONJ_DESC']=='Secció censal']
    barris = ad_boundaries[ad_boundaries['SCONJ_DESC']=='Barri']
    districts = ad_boundaries[ad_boundaries['SCONJ_DESC']=='Districte']
    barri_code = barris[['BARRI', 'NOM']]
    censal['NOM'] = censal['BARRI'].apply(
        lambda b: barri_code.loc[barri_code['BARRI'] == b, 'NOM'].iloc[0] 
        if (barri_code['BARRI'] == b).any() 
        else None
    )

    place = "Barcelona, Barcelona, Spain"
    # Download street network
    G = ox.graph_from_place(place, network_type="drive")
    edges = ox.graph_to_gdfs(G, nodes=False)
    
    censal = count_houses(parcels, censal, out_label = 'n_parcels', parcel_id_col ='parcel_id', apartments_col  = 'numberOfDwellings')
    censal = count_houses(flats, censal, out_label = 'n_flats', parcel_id_col ='id', apartments_col  = None)
    censal = count_houses(rooms, censal, out_label = 'n_rooms', parcel_id_col ='id', apartments_col  = None)
    censal['ratio_flats'] = 100*censal['n_flats'] / censal['n_parcels']
    censal['ratio_rooms'] = 100*censal['n_rooms'] / censal['n_parcels']
    censal['ratio'] = 100*(censal['n_flats']+censal['n_rooms']) / censal['n_parcels']
    
    barris = count_houses(parcels, barris, out_label = 'n_parcels', parcel_id_col ='parcel_id', apartments_col  = 'numberOfDwellings')
    barris = count_houses(flats, barris, out_label = 'n_flats', parcel_id_col ='id', apartments_col  = None)
    barris = count_houses(rooms, barris, out_label = 'n_rooms', parcel_id_col ='id', apartments_col  = None)
    barris['ratio_flats'] = 100*barris['n_flats'] / barris['n_parcels']
    barris['ratio_rooms'] = 100*barris['n_rooms'] / barris['n_parcels']
    barris['ratio'] = 100*(barris['n_flats']+barris['n_rooms']) / barris['n_parcels']
    
    districts = count_houses(parcels, districts, out_label = 'n_parcels', parcel_id_col ='parcel_id', apartments_col  = 'numberOfDwellings')
    districts = count_houses(flats, districts, out_label = 'n_flats', parcel_id_col ='id', apartments_col  = None)
    districts = count_houses(rooms, districts, out_label = 'n_rooms', parcel_id_col ='id', apartments_col  = None)
    districts['ratio_flats'] = 100*districts['n_flats'] / districts['n_parcels']
    districts['ratio_rooms'] = 100*districts['n_rooms'] / districts['n_parcels']
    districts['ratio'] = 100*(districts['n_flats']+districts['n_rooms']) / districts['n_parcels']


    censal.to_file('data/censal_sections.geojson', driver='GeoJSON')
    barris.to_file('data/barris.geojson', driver='GeoJSON')
    districts.to_file('data/districts.geojson', driver='GeoJSON')   
    edges.to_file('data/edges.geojson', driver='GeoJSON')