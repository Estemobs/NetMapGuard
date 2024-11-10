from subprocess import Popen, PIPE, STDOUT
import asyncio
import websockets
import subprocess
import json
import time
import requests
from bs4 import BeautifulSoup
import traceback

def getMyIP():
    ip_cmd = Popen("ipconfig", stdout=PIPE, stderr=STDOUT, shell=True)
    output, error = ip_cmd.communicate(timeout=4)
    output_split = output.decode("iso-8859-1").split('\r\n')
    ip = output_split[13].split(":")[1].replace(' ', '')
    return ip

my_ip = getMyIP()
my_home_coord = ""
blacklist = ["192.168.1.25", "192.168.1.254"]

all_ip = {}
all_ip[my_ip] = my_home_coord
all_ip['192.168.1.254'] = my_home_coord

print(all_ip)

def checkIP(ip):
    req = requests.get('https://scamalytics.com/ip/'+str(ip))
    soup = BeautifulSoup(req.text, 'html.parser')
    td = soup.find_all('td')
    for t in td:
        print(t.text, 1)
