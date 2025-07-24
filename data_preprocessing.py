import geopandas as gpd
import pandas as pd
from utils.utils import plot_ratio_map, censal_from_gdf, serpavi_from_gdf
import osmnx as ox
import os
import json
import requests
import gzip
import shutil
import numpy as np


# Load rental houses categories from JSON file
with open('data/houses_categories.json', 'r') as f_read:
    rental_houses = json.load(f_read)

def format_location_path(location_str):
    parts = location_str.lower().replace(" ", "").split(",")
    return "/".join(reversed(parts))


class city:
    def __init__(self, name, insideabnb_handle, date):
        self.name = name
        self.insideabnb_handle = insideabnb_handle
        self.date = date
        
        self.listings = None
        self.censal = None

        
        
###############################################
        
    def get_data(self):
        baseurl = "https://data.insideairbnb.com/spain/"
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

        
        listings = pd.read_csv(decompressed_path)
        listings['geometry'] = gpd.points_from_xy(listings['longitude'], listings['latitude'])
        listings = gpd.GeoDataFrame(listings, geometry='geometry', crs="EPSG:4326")
        listings['property_type_basic'] = listings['property_type'].apply(lambda x: 'Flat' if x in rental_houses else 'Room')
        listings['price'] = listings['price'].str.replace("$", "").str.replace(",", "").astype(float)
        listings['monthly_revenue'] = listings['estimated_revenue_l365d'] / 12
        self.listings = listings
        self.flats = listings[listings['property_type_basic'] == 'Flat']
        self.rooms = listings[listings['property_type_basic'] == 'Room']
        self.censal = censal_from_gdf(self.listings, target_wkid=102100)
        self.servapi = serpavi_from_gdf(self.listings)
        self.servapi['renta_total_VC'] = self.servapi['Cuantía_m']*self.servapi['Num_VC']
        self.servapi['renta_total_VU'] = self.servapi['Cuantía_1']*self.servapi['Num_VU']
        self.servapi = self.servapi[['renta_total_VC', 'renta_total_VU', 'Num_VC', 'Num_VU', 'CSEC', 'geometry']]
        self.servapi = self.servapi.rename(columns={
            'CSEC': 'csec',
        })
        self.servapi = self.servapi.dissolve(by='csec', aggfunc={
            'renta_total_VC': 'sum',
            'renta_total_VU': 'sum',
            'Num_VC': 'sum',
            'Num_VU': 'sum',
        }).reset_index()

        self.servapi['renta_media_VC'] = self.servapi['renta_total_VC'] / self.servapi['Num_VC']
        self.servapi['renta_media_VU'] = self.servapi['renta_total_VU'] / self.servapi['Num_VU']
        self.servapi['Num_V'] = self.servapi['Num_VC'] + self.servapi['Num_VU']
        self.servapi['renta_media_V'] = (self.servapi['renta_total_VC'] + self.servapi['renta_total_VU']) / self.servapi['Num_V']


################################################

    def count_houses(self, gdf, out_label):
        
        # Spatial join: count listings within each censal geometry
        counts = gpd.sjoin(gdf, self.censal, how='left', predicate='within').groupby('index_right').size()

        # Assign counts to censal GeoDataFrame
        self.censal[out_label] = self.censal.index.map(counts).fillna(0).astype(int)
        self.censal['mean_price'] = gpd.sjoin(self.listings, self.censal, how='left', predicate='within').groupby('index_right').agg({'price': 'mean'})
        self.censal['mean_revenue'] = gpd.sjoin(self.listings, self.censal, how='left', predicate='within').groupby('index_right').agg({'monthly_revenue': 'mean'})


 #############################################   
    
    
    def compute_ratios(self):
        """
        Computes the ratio of flats and rooms to parcels in the censal sections.
        """
        
        self.count_houses(self.flats, out_label='n_flats')
        self.count_houses(self.rooms, out_label='n_rooms')
        
        self.censal['n_all'] = self.censal['n_rooms'] + self.censal['n_flats']
        self.censal = self.censal[self.censal['viviendas'] > 0]
    
        # Calculate ratios
        self.censal['ratio_flats'] = 100 * self.censal['n_flats'] / self.censal['viviendas']
        self.censal['ratio_rooms'] = 100 * self.censal['n_rooms'] / self.censal['viviendas']
        self.censal['ratio'] =  self.censal['ratio_flats']+ self.censal['ratio_rooms']
        

###############################################

    def get_results(self, save_path=None):
        self.get_data()
        self.compute_ratios()
            
        out = self.servapi.drop(columns=['geometry']).merge(self.censal, how='left', on='csec').set_geometry('geometry')
        out['profit'] = out['mean_revenue'] - out['renta_media_V']
        out['net_profit'] = np.sign(out['profit'])
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            tosave = out
            tosave = tosave[['geometry', 'viviendas', 'n_flats', 'n_rooms', 'n_all', 'ratio_flats', 'ratio_rooms', 'ratio', 'mean_price', 'mean_revenue', 'profit', 'net_profit']]
            tosave.to_file(save_path, driver='GeoJSON')
        print("Computed ratios for flats and rooms in the city.")
        
    
       
##################################
##################################

def compute_city(city_name, insideabnb_handle, date, save_path):
    """
    Computes the Airbnb data and ratios for a given city.
    
    Parameters:
    - city_name: Name of the city.
    - province: Province of the city.
    - insideabnb_handle: Inside Airbnb handle for the city.
    - date: Date of the data to be used.
    - save_path: Optional path to save the results as GeoJSON.
    
    """
    c = city(city_name, insideabnb_handle, date)
    c.get_results(save_path)


if __name__ == "__main__":
    
   cities = pd.read_json('data/cities.json', lines=True)

   
   for _, row in cities.iterrows():
        city_name = row['city']
        insideabnb_handle = row['insideabnb_handle']
        date = row['dates']
       
        print(f"Processing {city_name}...")
        compute_city(city_name, insideabnb_handle, date, save_path=f"data/results/{city_name}.geojson")
        print(f"Finished processing {city_name}.")
