import geopandas as gpd
import pandas as pd
from utils.utils import arcgis_query_from_gdf
import osmnx as ox
import os
import json
import requests
import gzip
import shutil
import numpy as np
import tobler

#################################################


# Load rental houses categories from JSON file
with open('data/houses_categories.json', 'r') as f_read:
    rental_houses = json.load(f_read)

# Load layers configuration from JSON file
with open('data/layers_config.json', 'r') as f_read:
    layers_config = json.load(f_read)

#################################################
# Function to format location string into a path
# Example: "Barcelona, Spain" -> "spain/barcelona"
def format_location_path(location_str):
    parts = location_str.lower().replace(" ", "").split(",")
    return "/".join(reversed(parts))


################################################
################################################

class city:
    def __init__(self, name, insideabnb_handle, date):
        """
        Initializes a new instance of the class with the specified name, insideabnb handle, and date.
        Args:
            name (str): The name associated with the instance.
            insideabnb_handle (Any): The handle or identifier for InsideAirbnb data.
            date (Any): The date relevant to the instance.
        Attributes:
            listings (Any): Placeholder for listings data, initialized as None.
            censal (Any): Placeholder for censal data, initialized as None.
            servapi (Any): Placeholder for servapi data, initialized as None.
            renta (Any): Placeholder for renta data, initialized as None.
            dataset (Any): Placeholder for full dataset, initialized as None.
        """
        
        self.name = name
        self.insideabnb_handle = insideabnb_handle
        self.date = date
        
        self.listings = None
        self.censal = None
        self.servapi = None
        self.renta = None
        self.dataset = None       
###############################################
        
    def get_data(self):
        """
        Downloads, caches, and processes Airbnb listings data and enriches it with spatial and socioeconomic layers.
        Workflow:
        1. Constructs the download URL for Airbnb listings data based on the object's attributes.
        2. Downloads and caches the compressed CSV file if not already present.
        3. Decompresses the file and loads it into a GeoDataFrame.
        4. Processes listings data:
            - Converts coordinates to geometry.
            - Classifies property types as 'Flat' or 'Room'.
            - Cleans and converts price columns.
            - Calculates monthly revenue.
            - Projects data to EPSG:25830.
            - Splits listings into flats and rooms.
        5. Queries and processes additional spatial layers:
            - Censal: Aggregates census data by section.
            - Serpavi: Aggregates and computes income statistics by section.
            - Renta: Interpolates average income data to census sections using area-weighted interpolation.
        6. Stores processed data in instance attributes:
            - self.listings: All processed listings.
            - self.flats: Listings classified as flats.
            - self.rooms: Listings classified as rooms.
            - self.censal: Census data by section.
            - self.servapi: Socioeconomic data by section.
            - self.renta: Area-weighted interpolated income data by section.
        Raises:
            requests.HTTPError: If the data download fails.
            OSError: If file operations fail.
            ValueError: If data processing encounters unexpected formats.
        """
        
        
        
        baseurl = "https://data.insideairbnb.com/spain/"
        # Format the URL based on the insideabnb_handle
        url = baseurl + format_location_path(self.insideabnb_handle) + "/" + self.date +"/data/listings.csv.gz"

        # Set the paths for compressed and decompressed files
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

        # Load the listings data into a GeoDataFrame and process it
        listings = pd.read_csv(decompressed_path)
        listings['geometry'] = gpd.points_from_xy(listings['longitude'], listings['latitude'])
        listings = gpd.GeoDataFrame(listings, geometry='geometry', crs="EPSG:4326")
        listings['property_type_basic'] = listings['property_type'].apply(lambda x: 'Flat' if x in rental_houses else 'Room')
        listings['price'] = listings['price'].str.replace("$", "").str.replace(",", "").astype(float)
        listings['monthly_revenue'] = listings['estimated_revenue_l365d'] / 12
        self.listings = listings.to_crs("EPSG:25830")
        
        # Split listings into flats and rooms
        self.flats = listings[listings['property_type_basic'] == 'Flat'].to_crs("EPSG:25830")
        self.rooms = listings[listings['property_type_basic'] == 'Room'].to_crs("EPSG:25830")
        
        # Query and process additional spatial layers
        ############### CENSAL, SERPAVI, and RENTA ##################
        
        # Query and process Censal data
        cfg = layers_config["censal"]
        self.censal = arcgis_query_from_gdf(
            self.listings,
            url=cfg["url"],
            target_epsg=cfg["epsg"],
            use_json_geometry=cfg["use_json_geometry"],
            include_inSR=cfg["include_inSR"]
        ).to_crs("EPSG:25830")
        self.censal = self.censal[['csec', 'geometry', 'viviendas']]  # Keep only necessary columns
        self.censal = self.censal.dissolve(by='csec', aggfunc='sum').reset_index() # Aggregate by csec (codigo sección censal)
        self.censal['mean_price'] = gpd.sjoin(self.listings, self.censal, how='left', predicate='within').groupby('index_right').agg({'price': 'mean'}) # Compute the mean price of listings within each censal geometry
        self.censal['mean_revenue'] = gpd.sjoin(self.listings, self.censal, how='left', predicate='within').groupby('index_right').agg({'monthly_revenue': 'mean'}) # Compute the mean monthly revenue of listings within each censal geometry
        
        # Query and process SERPAVI data
        cfg = layers_config["serpavi"]
        self.servapi = arcgis_query_from_gdf(
            self.listings,
            url=cfg["url"],
            target_epsg=cfg["epsg"],
            use_json_geometry=cfg["use_json_geometry"],
            include_inSR=cfg["include_inSR"]
        ).to_crs("EPSG:25830")
        self.servapi['renta_total_VC'] = self.servapi['Cuantía_m']*self.servapi['Num_VC'] # Compute the total rent for flats in the geometry
        self.servapi['renta_total_VU'] = self.servapi['Cuantía_1']*self.servapi['Num_VU'] # Compute the total rent for houses in the geometry
        self.servapi = self.servapi[['renta_total_VC', 'renta_total_VU', 'Num_VC', 'Num_VU', 'CSEC', 'geometry']] # Keep only necessary columns
        self.servapi = self.servapi.rename(columns={
            'CSEC': 'csec',
        }) # Rename CSEC to csec for consistency with censal data
        
        self.servapi = self.servapi.dissolve(by='csec', aggfunc={
            'renta_total_VC': 'sum',
            'renta_total_VU': 'sum',
            'Num_VC': 'sum',
            'Num_VU': 'sum',
        }).reset_index() # Aggregate by csec (codigo sección censal)

        # We compute ponderated averages for rent
        self.servapi['renta_media_VC'] = self.servapi['renta_total_VC'] / self.servapi['Num_VC'] # Compute the average rent for flats in the geometry
        self.servapi['renta_media_VU'] = self.servapi['renta_total_VU'] / self.servapi['Num_VU'] # Compute the average rent for houses in the geometry
        self.servapi['Num_V'] = self.servapi['Num_VC'] + self.servapi['Num_VU'] # Total number of properties in the geometry
        self.servapi['renta_media_V'] = (self.servapi['renta_total_VC'] + self.servapi['renta_total_VU']) / self.servapi['Num_V'] # Compute the average rent for all properties in the geometry


        # Query and process RENTA data
        cfg = layers_config["renta"]
        self.renta = arcgis_query_from_gdf(
            self.listings,
            url=cfg["url"],
            target_epsg=cfg["epsg"],
            use_json_geometry=cfg["use_json_geometry"],
            include_inSR=cfg["include_inSR"]
        ).to_crs("EPSG:25830")
        
        self.renta = self.renta[['SSCC_FilterDatabase_Renta_p_202', 'geometry']] # Keep only necessary columns (2020 data)
        self.renta = self.renta.rename(columns={
            'SSCC_FilterDatabase_Renta_p_202': 'ingresos_medios'
        }) # Rename to 'ingresos_medios' for consistency
        self.renta['geometry'] = self.renta['geometry'].buffer(0) # Fix geometries by buffering with 0
        self.renta = tobler.area_weighted.area_interpolate( # Area-weighted interpolation of income data onto census sections
            self.renta.to_crs(self.censal.crs),
            self.censal,
            intensive_variables=['ingresos_medios']
        ).merge(self.censal[['geometry', 'csec']], on='geometry', how='left') # Merge with censal data to get csec
        

################################################

    def count_houses(self, gdf, out_label):
        """
        Counts the number of geometries in the input GeoDataFrame (`gdf`) that fall within each geometry of the `self.censal` GeoDataFrame,
        and assigns the counts to a new column in `self.censal`.
        Parameters
        ----------
        gdf : geopandas.GeoDataFrame
            The GeoDataFrame containing the geometries (e.g., houses or listings) to be counted within each censal geometry.
        out_label : str
            The name of the column to be added to `self.censal` where the counts will be stored.
        Returns
        -------
        None
            The method updates `self.censal` in place by adding a new column with the counts.
        """
       
        
        # Spatial join: count listings within each censal geometry
        counts = gpd.sjoin(gdf, self.censal, how='left', predicate='within').groupby('index_right').size()

        # Assign counts to censal GeoDataFrame
        self.censal[out_label] = self.censal.index.map(counts).fillna(0).astype(int)
        


 #############################################   
    
    
    def compute_ratios(self):
        """
        Computes and adds ratio columns to the `self.censal` DataFrame based on the number of flats and rooms.
        This method performs the following steps:
        1. Counts the number of flats and rooms using `self.count_houses` and stores them in the 'n_flats' and 'n_rooms' columns, respectively.
        2. Calculates the total number of units ('n_all') as the sum of flats and rooms.
        3. Filters the DataFrame to include only rows where the 'viviendas' column is greater than 0.
        4. Calculates the percentage ratios of flats and rooms with respect to 'viviendas' and stores them in 'ratio_flats' and 'ratio_rooms'.
        5. Computes the total ratio as the sum of 'ratio_flats' and 'ratio_rooms', storing it in the 'ratio' column.
        Assumes that `self.censal` is a pandas DataFrame with at least the columns 'viviendas', 'n_flats', and 'n_rooms'.
        """
        
        
        self.count_houses(self.flats, out_label='n_flats') # Count flats in censal geometries
        self.count_houses(self.rooms, out_label='n_rooms') # Count rooms in censal geometries
        
        self.censal['n_all'] = self.censal['n_rooms'] + self.censal['n_flats'] # Total number of units in the geometry
        self.censal = self.censal[self.censal['viviendas'] > 0] # Filter out geometries with no viviendas
    
        # Calculate ratios
        self.censal['ratio_flats'] = 100 * self.censal['n_flats'] / self.censal['viviendas'] # Percentage of flats in the geometry
        self.censal['ratio_rooms'] = 100 * self.censal['n_rooms'] / self.censal['viviendas'] # Percentage of rooms in the geometry
        self.censal['ratio'] =  self.censal['ratio_flats']+ self.censal['ratio_rooms'] # Total ratio of flats and rooms in the geometry
        

###############################################

    def get_results(self, save_path=None):
        """
        Computes and merges various datasets to produce a geospatial DataFrame with calculated ratios and profit metrics.
        This method performs the following steps:
        1. Retrieves and processes data required for analysis.
        2. Computes ratios related to flats and rooms.
        3. Merges processed data with census and income datasets.
        4. Calculates profit and net profit metrics for each spatial unit.
        5. Converts the resulting GeoDataFrame to the EPSG:4326 coordinate reference system.
        6. Optionally saves the resulting data as a GeoJSON file if a save path is provided.
        Parameters
        ----------
        save_path : str, optional
            The file path where the resulting GeoDataFrame should be saved as a GeoJSON file. If None, the file is not saved.
        Returns
        -------
        None
        Side Effects
        ------------
        - Prints a message upon successful computation.
        - Optionally writes a GeoJSON file to disk.
        """
        
        self.get_data() # Retrieve and process data
        self.compute_ratios() # Compute ratios for flats and rooms
            
        out = self.servapi.drop(columns=['geometry']).merge(self.censal, how='left', on='csec').set_geometry('geometry') # Merge socioeconomic data with census data
        out = self.renta.merge(out, how='left', on='geometry') # Merge income data with the previous result
        out['profit'] = out['mean_revenue'] - out['renta_media_V'] # Calculate profit as the difference between mean revenue and average income
        out['net_profit'] = np.sign(out['profit']) # Assign net profit as 1 if profit is positive, -1 if negative, and 0 if zero
        out = out.to_crs("EPSG:4326")
        self.dataset = out[['geometry', 'viviendas', 'n_flats', 'n_rooms', 'n_all', 'ratio_flats', 'ratio_rooms', 
                             'ratio', 'mean_price', 'mean_revenue', 'profit', 'net_profit', 'ingresos_medios']]

        if save_path: # Save the results to a GeoJSON file if a save path is provided
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            self.dataset.to_file(save_path, driver='GeoJSON')
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

   cities = pd.read_json('data/cities.json', lines=True) # Load cities data from JSON file

   
   for _, row in cities.iterrows(): # Iterate through each city in the DataFrame
        # Extract city name, Inside Airbnb handle, and date from the row
        city_name = row['city']
        insideabnb_handle = row['insideabnb_handle']
        date = row['dates']
       
        print(f"Processing {city_name}...")
        compute_city(city_name, insideabnb_handle, date, save_path=f"data/results/{city_name}.geojson")
        print(f"Finished processing {city_name}.")
