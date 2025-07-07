import geopandas as gpd
import requests
from shapely.geometry import box
import osmnx as ox
from osmnx._errors import InsufficientResponseError
from tobler.util import h3fy
import pandas as pd
from tqdm import tqdm
from .settings import Settings, Headers
tqdm.pandas()
import xml.etree.ElementTree as ET
import os
import zipfile
from io import BytesIO

##############################################
def parse_atom(url):
    """
    Fetches and parses an Atom feed from the given URL.
    Args:
        url (str): The URL of the Atom feed to fetch and parse.
    Returns:
        xml.etree.ElementTree.Element: The root element of the parsed Atom feed.
    Raises:
        requests.HTTPError: If the HTTP request to the URL fails.
        xml.etree.ElementTree.ParseError: If the response content is not valid XML.
    """
   
    response = requests.get(url)
    response.raise_for_status()
    return ET.fromstring(response.content)


#############################################
#############################################

class ATOM_Query():
    def __init__(self, province_name, municipality_name):
        self._province_name = province_name
        self._municipality_name = municipality_name
        print(f"Collecting features for municipalities containing '{self.municipality_name}' in '{self.province_name}'")
        self._province_title, self._province_feed_url = self.find_province_feed()
        self._municipality_title, self._municipality_zip_url = self.find_municipality_zip_url()

    ##################################################
    
    @property
    def province_name(self):
        return self._province_name

    @property
    def municipality_name(self):
        return self._municipality_name

    @property
    def province_title(self):
        return self._province_title

    @property
    def province_feed_url(self):
        return self._province_feed_url

    @property
    def municipality_title(self):
        return self._municipality_title

    @property
    def municipality_zip_url(self):
        return self._municipality_zip_url

    ##################################################

    def find_province_feed(self):
        root = parse_atom(Settings.ATOM_URL)
        hrefs = []
        titles = []
        for entry in root.findall('atom:entry',Headers.ATOM_NS):
            title = entry.find('atom:title', Headers.ATOM_NS).text.strip()
            if self.province_name.lower() in title.lower():
                link = entry.find('atom:link', Headers.ATOM_NS)
                href = link.attrib.get('href', '')
                rel = link.attrib.get('rel', '')
                if rel == 'enclosure' and href.endswith('.xml'):
                    hrefs.append(href)
                    titles.append(title)

        if len(hrefs) > 0:
            if len(hrefs) == 1:
                return titles[0], hrefs[0]
            else:
                print(f"Multiple feeds found for '{self.province_name}': {len(hrefs)}")
                print("Available feeds:")
                for i, href in enumerate(hrefs):
                    print(f"{i+1}: {title}: {href}")
                raise Exception(f"Multiple feeds found for '{self.province_name}'. Please specify one.")
        else:
            raise Exception(f"Province '{self.province_name}' not found in main feed.")

    ##################################################

    def find_municipality_zip_url(self):
        root = parse_atom(self.province_feed_url)
        hrefs =[]
        titles =[]
        for entry in root.findall('atom:entry', Headers.ATOM_NS):
            title_elem = entry.find('atom:title', Headers.ATOM_NS)
            if title_elem is not None:
                title = title_elem.text.strip()
                if self.municipality_name.lower() in title.lower():
                    for link in entry.findall('atom:link', Headers.ATOM_NS):
                        href = link.attrib.get('href', '')
                        rel = link.attrib.get('rel', '')
                        if href.endswith('.zip') and rel == 'enclosure':
                            hrefs.append(href)
                            titles.append(title)

        if len(hrefs) > 0:
            if len(hrefs) == 1:
                return titles[0], hrefs[0]
            else:
                print(f"Multiple feeds found for '{self.municipality_name}': {len(hrefs)}")
                print("Please specify one.")
                print("Available feeds:")
                for i, href in enumerate(hrefs):
                    print(f"{i+1}: {title}: {href}")
                return None, None
        else:
            raise Exception(f"Municipality '{self.municipality_name}' not found in main feed.")

    ##################################################  

    def download_gml(self, output_dir="inspire_data"):
        response = requests.get(self.municipality_zip_url)
        response.raise_for_status()
        municipality_folder = os.path.join(output_dir, os.path.basename(self.municipality_zip_url))
        os.makedirs(municipality_folder, exist_ok=True)

        with zipfile.ZipFile(BytesIO(response.content)) as z:
            z.extractall(municipality_folder)
            gml_files = [f for f in z.namelist() if f.endswith('.gml')]
            if not gml_files:
                raise Exception("No GML file found in ZIP.")
            gml_path = os.path.join(municipality_folder, gml_files[0])
            return gpd.read_file(gml_path)