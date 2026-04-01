from subprocess import Popen, PIPE, STDOUT
import asyncio
import websockets
import subprocess
import json
import time
import requests
from bs4 import BeautifulSoup
import traceback

# get local ip
def getMyIP():
    ip_cmd = Popen('ipconfig', stdout = PIPE, stderr = STDOUT, shell = True)
    output, error = ip_cmd.communicate(timeout=4)
    output_split = output.decode("iso-8859-1").split('\r\n')
    print(output_split)
    ip = output_split[12].split(':')[1].replace(' ','')
    return ip

my_ip = getMyIP()
print("MyIp", my_ip)

# local gps loc
my_home_coord = "44.2719,5.2715"

# blacklist local device
blacklist = ['192.168.1.25','192.168.1.254']

# dict to store all ip for each trame
all_ip = {}

all_ip[my_ip] = my_home_coord
all_ip['192.168.1.254'] = my_home_coord
print(all_ip)

def checkIP(ip):

    #print("try "+str(ip))
    req = requests.get('https://scamalytics.com/ip/'+str(ip))
    soup = BeautifulSoup(req.text, 'html.parser')

    td = soup.find_all('td')
    i = 0
    for t in td:
        #print(t.text, i)
        i += 1
    if len(td) == 0:
        return "SCAM REQ ERR"
    else:
        hostname = td[0].text
        asn = td[1].text
        isp = td[2].text
        country = td[5].text
        region = td[7].text
        city = td[8].text

        lat = td[12].text
        lng = td[13].text

        domain_name = ""

        if td[14].text == "N/A":
            print("PORT SCAN N/A")
        else:

            #print("LEN :: >> "+str(len(td)))
            http = td[14].text
            ssl_http = td[15].text
            http_proxy = td[16].text
            opsmsg = td[17].text
            tor_orport = td[18].text
            tcp_udp = td[19].text
            ssh = td[20].text

            ano_vpn = td[21].text
            tor_exit_node = td[22].text
            server = td[23].text
            public_proxy = td[24].text
            web_proxy = td[25].text
            search_eng_bot = td[26].text

            domain_name = td[27].text

        # rep
        # div.container:nth-child(3) > div:nth-child(5) > pre:nth-child(2)
        # /html/body/div[3]/div[4]/pre

        rep = soup.select('div.container:nth-child(3) > div:nth-child(5) > pre:nth-child(2)')
        rep = str(rep)[53:-16]
        load_j = json.loads(str(rep))
        ip_rep_loc = load_j['score']+" "+load_j['risk']+" "+hostname+" "+asn+" "+isp+" "+domain_name
        all_ip[ip] = lat+","+lng
        ip_rep_loc = ip_rep_loc.rstrip()
        #print(ip_rep_loc)
        return ip_rep_loc

p = Popen('tshark.exe -i ethernet', stdout = PIPE, stderr = STDOUT, shell = True)

req_id = ""
req_time = ""
req_src = ""
req_dst = ""
req_protocol = ""
req_len = ""
req_info = ""
req_port = ""
req_dst_port = ""

async def ws_handler(websocket, path):
    while True:

        line = p.stdout.readline().decode('utf-8')
        line = line.strip()

        line = line.replace('  ',' ')
        #print(line)
        if not line:
            break

        line_split = line.split(' ')

        print(line_split, len(line_split), websocket)
        try:
            req_id = line_split[0]
            req_time = line_split[2]
            req_src = line_split[3]
            req_dst = line_split[5]
            req_protocol = line_split[6]
            req_len = line_split[1]
            """
            req_port = line_split[8]
            req_dst_port = ""

            if len(line_split)>9:
                req_dst_port = line_split[10]
            """

            ip_rep_loc = ""
            if req_src not in blacklist and '.' in req_src:
                ip_rep_loc = checkIP(req_src)

            if req_dst not in blacklist and '.' in req_dst:
                ip_rep_loc = checkIP(req_dst)

            #print(all_ip)
            if '.' in req_src and '.' in req_dst:
                to_send = all_ip[req_src]+" "+all_ip[req_dst]+" "+req_src+" "+req_dst+ip_rep_loc
                #print(to_send)

                await websocket.send(to_send)
                await asyncio.sleep(0.1)
        except Exception as e:
            print(traceback.format_exc())


start_ws = websockets.serve(ws_handler, "localhost", 8080)
asyncio.get_event_loop().run_until_complete(start_ws)
asyncio.get_event_loop().run_forever()
