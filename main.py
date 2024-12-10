import subprocess
import requests
import dash
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import streamlit as st
from folium import Map, Marker
from bs4 import BeautifulSoup
from folium import Map, Marker

# Blacklist des IP suspectes
blacklist = ["192.168.1.25", "192.168.1.254"]


# Fonction pour récupérer les connexions actives via netstat
def get_active_connections():
    try:
        # Exécution de la commande netstat
        process = subprocess.Popen(["netstat", "-an"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output, error = process.communicate()

        if error:
            print(f"Erreur lors de l'exécution de netstat : {error}")
            return []

        # Extraction des IP distantes (colonnes 3 et 4 pour IPv4)
        connections = []
        for line in output.splitlines():
            if "ESTABLISHED" in line or "SYN_SENT" in line:  # Connexions actives
                parts = line.split()
                if len(parts) > 2:
                    remote_ip = parts[2].split(':')[0]
                    if remote_ip not in ["127.0.0.1", "::1"]:  # Exclure localhost
                        connections.append(remote_ip)

        return list(set(connections))  # Suppression des doublons
        

    except Exception as e:
        print(f"Erreur lors de la récupération des connexions actives : {e}")
        return []

def create_streamlit_app():
       st.title("NetMapGuard")
       # Afficher les connexions actives
       st.subheader("Connexions actives")
       st.write(f"IP actives détectées : {get_active_connections}")
       
       # Afficher la carte
       st.subheader("Carte")
       st.plotly_chart(go.Figure(data=[go.Scattermapbox(
           lat=[coord[0] for coord in coordinates.values()],
           lon=[coord[1] for coord in coordinates.values()],
           mode='markers',
           marker=go.scattermapbox.Marker(size=9),
           text=[f"IP: {ip}" for ip, coord in coordinates.items() if coord],
           hoverinfo='text'
       )]))

       # Afficher la liste des IP
       st.subheader("Liste des IP")
       for ip, coord in coordinates.items():
           color = 'green' if coord else 'red'
           st.write(f"{ip}: {'Localisée' if coord else 'Non localisée'} (Couleur: {color})")

# Créer et exécuter l'application Streamlit
if __name__ == '__main__':
        create_streamlit_app()


def create_dash_app():
       app = dash.Dash(__name__)
       
       @app.callback(
           Output('map', 'children'),
           [Input('ip-input', 'value')])
       def update_map(ip):
           coordinates = getIPCoordinates(ip)
           if coordinates:
               return go.Scattermapbox(
                   lat=[coordinates[0]],
                   lon=[coordinates[1]],
                   mode='markers',
                   marker=go.scattermapbox.Marker(size=9),
                   text=[f"IP: {ip}"],
                   hoverinfo='text'
               )
           else:
               return go.Scattermapbox(
                   lat=[None],
                   lon=[None],
                   mode='markers',
                   marker=go.scattermapbox.Marker(size=9),
                   text=['IP non localisée'],
                   hoverinfo='text'
               )   


# Sauvegarde de la carte dans un fichier HTML
m.save("carte_monde.html")
print("Carte enregistrée : carte_monde.html")
