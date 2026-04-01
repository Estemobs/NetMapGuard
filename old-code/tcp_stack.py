from subprocess import Popen, PIPE, STDOUT
import os
import curses
import traceback
import sys

p = Popen('tshark.exe -i ethernet', stdout = PIPE,
        stderr = STDOUT, shell = True)


cursol = curses.initscr()

curses.start_color()
curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)




# ip_src : [ip_dst, req, total_paquet_size]
trafic_dict ={
}



def main(cur):
    while True:

        req_id = ""
        req_time = ""
        req_src = ""
        req_dst = ""
        req_protocol = ""
        req_len = ""
        req_info = ""
        req_port = ""
        req_dst_port = ""


        line = p.stdout.readline().decode('utf-8').strip()
        line = line.replace("→","")
        line = line.replace("  "," ")
        line = line.replace("  "," ")

        if not line:
          break
        try:
          line_split = line.split(" ")
          #print(line)
          if len(line_split)>10:
              req_id = line_split[0]
              req_time = line_split[1]
              req_src = line_split[2]
              req_dst = line_split[3]
              req_protocol = line_split[4]
              req_len = line_split[5]

              req_port = line_split[7]
              req_dst_port = line_split[8]



          if len(line_split)>15:
              req_info = line_split[11]+" "+line_split[12]+" "+line_split[13]+" "+line_split[14]+" "+line_split[15]
          if req_src in trafic_dict.keys():
              trafic_dict[req_src][1] += 1
              print(req_len)
              trafic_dict[req_src][2] += int(req_len)/1000
          else:
              trafic_dict[req_src] = [req_dst, 1, int(req_len)/1000]

          line_h = 0
          for key in trafic_dict:
            line_h += 1
            cursol.addstr(line_h,0,key+ " -> "+trafic_dict[key][0]+" "+ str(trafic_dict[key][1])+" "+ str(trafic_dict[key][2])+"\n")
          cursol.refresh()
          cursol.clear()
        except Exception:
            cursol.addstr(1,0,"err :: \n")
            cursol.refresh()


curses.wrapper(main)

      #print(req_id,req_time,req_src,req_dst,req_protocol,req_len,req_port,req_dst_port,req_info)
