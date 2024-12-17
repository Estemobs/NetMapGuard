import subprocess
import requests
from bs4 import BeautifulSoup
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.web import RequestHandler, Application

def get_active_connections():
    try:
        process = subprocess.Popen(["netstat", "-an"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output, _ = process.communicate()

        connections = set()
        for line in output.splitlines():
            if "ESTABLISHED" in line or "SYN_SENT" in line:
                parts = line.split()
                if len(parts) > 4:
                    remote_ip = parts[4].split(':')[0]
                    if remote_ip not in ["127.0.0.1", "::1"]:
                        connections.add(remote_ip)
        return list(connections)
    except Exception as e:
        print(f"Erreur lors de l'analyse de l'IP : {e}")
        return []

def checkIP(ip):
    try:
        req = requests.get(f'https://scamalytics.com/ip/{ip}')
        soup = BeautifulSoup(req.text, 'html.parser')
        td = soup.find_all('td')
        for t in td:
            if "Risk Score" in t.text:
                score = int(t.text.split()[-1])
                if score < 30:
                    return "green"
                elif score < 70:
                    return "orange"
                else:
                    return "red"
        return "unknown"
    except Exception as e:
        print(f"Erreur lors de l'analyse de l'IP {ip} : {e}")
        return "unknown"

def getIPCoordinates(ip):
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}")
        data = response.json()
        if data["status"] == "success":
            danger_level = checkIP(ip)
            return (data["lat"], data["lon"], data["city"], danger_level, data.get("org", "Unknown"))
        else:
            print(f"Impossible de récupérer les coordonnées pour l'IP {ip}")
            return None
    except Exception as e:
        print(f"Erreur lors de la récupération des coordonnées de {ip}: {e}")
        return None

coordinates = {}
danger_levels = {}
organizations = {}

def update_coordinates():
    active_ips = get_active_connections()
    print(f"IP actives détectées : {active_ips}")

    for ip in active_ips:
        coord = getIPCoordinates(ip)
        if coord:
            coordinates[ip] = coord[:3]
            danger_levels[ip] = coord[3]
            organizations[ip] = coord[4]
        else:
            coordinates[ip] = None
            danger_levels[ip] = "unknown"
            organizations[ip] = "Unknown"

class MainHandler(RequestHandler):
    def get(self):
        self.write("""
        <html>
        <head>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body, html { margin: 0; padding: 0; width: 100%%; height: 100%%; display: flex; flex-direction: column; }
                #map { width: 100%%; flex-grow: 1; }
                #coordinates { width: 100%%; height: 25%%; overflow: auto; background: rgba(255, 255, 255, 0.8); }
                #divider { width: 100%%; height: 5px; background: #ccc; cursor: ns-resize; }
            </style>
        </head>
        <body>
            <div id="map"></div>
            <div id="divider"></div>
            <div id="coordinates">
                <ul id="ip-list"></ul>
            </div>
            <script>
                function updateMap() {
                    fetch('/data').then(response => response.json()).then(data => {
                        var latitudes = data.coordinates.map(coord => coord ? coord[0] : null);
                        var longitudes = data.coordinates.map(coord => coord ? coord[1] : null);
                        var cities = data.coordinates.map(coord => coord ? coord[2] : null);
                        var texts = data.ips.map((ip, index) => `IP: ${ip}, City: ${cities[index]}, Coordinates: (${latitudes[index]}, ${longitudes[index]}), Danger Level: ${data.danger_levels[index]}, Organization: ${data.organizations[index]}`);
                        var colors = data.danger_levels.map(level => {
                            if (level === 'green') return 'green';
                            if (level === 'orange') return 'orange';
                            if (level === 'red') return 'red';
                            return 'black';
                        });

                        var plotData = [{
                            type: 'scattermapbox',
                            lat: latitudes.filter(lat => lat !== null),
                            lon: longitudes.filter(lon => lon !== null),
                            mode: 'markers',
                            marker: { size: 12, color: colors.filter((_, index) => latitudes[index] !== null) },
                            text: texts.filter((_, index) => latitudes[index] !== null),
                            hoverinfo: 'text'
                        }];
                        var layout = {
                            mapbox: { style: 'open-street-map', center: { lat: 47.218371, lon: -1.553621 }, zoom: 2 },
                            showlegend: false,
                            margin: { t: 0, b: 0, l: 0, r: 0 }
                        };
                        Plotly.newPlot('map', plotData, layout);

                        var ipList = document.getElementById('ip-list');
                        ipList.innerHTML = '';
                        data.ips.forEach((ip, index) => {
                            var li = document.createElement('li');
                            if (latitudes[index] !== null && longitudes[index] !== null) {
                                li.textContent = `IP: ${ip}, City: ${cities[index]}, Coordinates: (${latitudes[index]}, ${longitudes[index]}), Danger Level: ${data.danger_levels[index]}, Organization: ${data.organizations[index]}`;
                            } else {
                                li.textContent = `IP: ${ip}, Coordinates: Not found, Danger Level: ${data.danger_levels[index]}, Organization: ${data.organizations[index]}`;
                            }
                            ipList.appendChild(li);
                        });
                    });
                }
                setInterval(updateMap, 10000);
                updateMap();

                const divider = document.getElementById('divider');
                let isResizing = false;

                divider.addEventListener('mousedown', function(e) {
                    isResizing = true;
                    document.addEventListener('mousemove', resize);
                    document.addEventListener('mouseup', stopResize);
                });

                function resize(e) {
                    if (!isResizing) return;
                    const map = document.getElementById('map');
                    const coordinates = document.getElementById('coordinates');
                    const totalHeight = window.innerHeight;
                    const newMapHeight = e.clientY;
                    const newCoordinatesHeight = totalHeight - newMapHeight - divider.offsetHeight;
                    map.style.height = newMapHeight + 'px';
                    coordinates.style.height = newCoordinatesHeight + 'px';
                }

                function stopResize() {
                    isResizing = false;
                    document.removeEventListener('mousemove', resize);
                    document.removeEventListener('mouseup', stopResize);
                }
            </script>
        </body>
        </html>
        """)

class DataHandler(RequestHandler):
    def get(self):
        self.write({
            "ips": list(coordinates.keys()),
            "coordinates": list(coordinates.values()),
            "danger_levels": list(danger_levels.values()),
            "organizations": list(organizations.values())
        })

def make_app():
    return Application([
        (r"/", MainHandler),
        (r"/data", DataHandler),
    ])

if __name__ == "__main__":
    app = make_app()
    app.listen(8888)
    periodic_callback = PeriodicCallback(update_coordinates, 10000)
    periodic_callback.start()
    IOLoop.current().start()


