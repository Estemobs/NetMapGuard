from subprocess import Popen, PIPE, STDOUT

p = Popen('tshark.exe -i ethernet', stdout = PIPE,
        stderr = STDOUT, shell = True)


req_id = ""
req_time = ""
req_src = ""
req_dst = ""
req_protocol = ""
req_len = ""
req_info = ""
req_port = ""
req_dst_port = ""

while True:

  line = p.stdout.readline().decode('utf-8').strip()

  if not line:
      break

  line_split = line.split(' ')
  print(line)
  """
  if len(line_split)>15:
      req_id = line_split[0]
      req_time = line_split[2]
      req_src = line_split[3]
      req_dst = line_split[5]
      req_protocol = line_split[6]
      req_len = line_split[7]

      req_port = line_split[8]
      req_dst_port = line_split[10]
      req_info = line_split[11]+" "+line_split[12]+" "+line_split[13]+" "+line_split[14]+" "+line_split[15]

      print(req_id,req_time,req_src,req_dst,req_protocol,req_len,req_port,req_dst_port,req_info)
      if "94" in req_dst:
          print(req_dst)
          """
