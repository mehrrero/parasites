



class Settings:
    WFS_URL = 'http://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx' # WFS endpoint for Cadastral Parcels 
    CRS = 'EPSG:25830' #Geographic CRS to demand results
    H3_ZOOM = 9 #H3_Zoom for the wfs grid
    ATOM_URL = "https://www.catastro.hacienda.gob.es/INSPIRE/buildings/ES.SDGC.bu.atom.xml"

class Headers:
    ATOM_NS = {'atom': 'http://www.w3.org/2005/Atom'}