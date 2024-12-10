import subprocess
import requests
from bs4 import BeautifulSoup
from gmplot import gmplot

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

# Fonction pour vérifier une IP avec Scamalytics
def checkIP(ip):
    try:
        req = requests.get(f'https://scamalytics.com/ip/{ip}')
        soup = BeautifulSoup(req.text, 'html.parser')
        td = soup.find_all('td')
        print(f"Analyse pour l'IP {ip}:")
        for t in td:
            print(t.text)
    except Exception as e:
        print(f"Erreur lors de l'analyse de l'IP {ip} : {e}")

# Fonction pour obtenir les coordonnées géographiques d'une IP
def getIPCoordinates(ip):
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}")
        data = response.json()
        if data["status"] == "success":
            return (data["lat"], data["lon"])
        else:
            print(f"Impossible de récupérer les coordonnées pour l'IP {ip}")
            return None
    except Exception as e:
        print(f"Erreur lors de la récupération des coordonnées de {ip}: {e}")
        return None

# Récupération des connexions actives
active_ips = get_active_connections()
print(f"IP actives détectées : {active_ips}")

# Récupération des coordonnées pour toutes les IP
coordinates = {}
for ip in active_ips:
    if ip not in blacklist:
        coord = getIPCoordinates(ip)
        if coord:
            coordinates[ip] = coord
    else:
        coordinates[ip] = None  # IP suspecte, coordonnées non récupérées

# Création de la carte avec gmplot
gmap = gmplot.GoogleMapPlotter(20, 0, 2, apikey="VOTRE_CLE_API_GOOGLE_MAPS")  # Carte centrée globalement

# Ajout des points sur la carte
for ip, coord in coordinates.items():
    if coord:
        color = 'green' if ip not in blacklist else 'red'
        gmap.marker(coord[0], coord[1], color=color)
        print(f"Ajout de l'IP {ip} à la carte aux coordonnées {coord}.")

# Sauvegarde de la carte dans un fichier HTML
gmap.draw("carte_monde.html")
print("Carte enregistrée : carte_monde.html")
