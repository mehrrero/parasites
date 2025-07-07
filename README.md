# Parasites: A visualization of the touristic Airbnb invasion in Barcelona

This repository contains the data for the streamlit app hosted [here](https://parasites.streamlit.app/).

The idea for this analysis was brought to me after this reading this [news piece from El País](https://elpais.com/economia/2025-07-02/donde-estan-los-casi-400000-pisos-turisticos-de-espana-el-mapa-calle-a-calle.html). Here, they report, by using public data released by the [Spanish Institute of Statistics](https://www.ine.es/),  surprisingly low numbers of touristic appartments and housing in Barcelona. In particular, they claim that the largest values they find don't even reach 3% of occupation.

> En Barcelona, Ciutat Vella y el Eixample son las zonas con más peso de la vivienda turística: 2,8% y 2,9%, respectivamente. El Eixample, más extenso, suma unos 4.000 alojamientos, cuatro veces más que Ciutat Vella.

This is clear contrast to the everyday feeling that any person residing in Barcelona can have. Hence, I decided to take a look at a different source of data, provided by the [Spanish Cadastre](https://www.catastro.hacienda.gob.es/webinspire/index.html) in combination with a well known scrapper of [Airbnb data](https://insideairbnb.com/get-the-data/). My results indeed indicate that there are parts of the city where the percentage of apartments fully dedicated to airbnb is close to 20%, while this number escalates to 30% if we include those that are rented by rooms.

## How to reproduce these results

1. Download the Barcelona listings file from [Inside Airbnb](https://insideairbnb.com/get-the-data/) and place it as `barcelona.csv` in `data`.
2. Run `python data_preprocessing.py`. This will produce the datasets with results as `geoJSON` files.
3. The dashboard can be run locally by `streamlit run app.py`.
