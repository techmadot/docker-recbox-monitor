import time
import subprocess
import re
import requests
import json
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

## InfluxDBが動いているアドレス.今回は自分自身.
url = "http://127.0.0.1:8086"
## 使用する Organization
orgs = "myorgs"
## 使用する Bucket
bucket = "mybucket"
## 事前に設定したトークン.
token = "my-recmachine-token"
## 録画ファイルを置くディレクトリ.
record_dir = "/record-data"
## EPGStationが動作しているアドレス.
epgstation_url="http://127.0.0.1:8888"
## Mirakurunが動作しているアドレス.
mirakurun_url='http://127.0.0.1:40772'

def get_cpu_usage():
  with open('/proc/stat', 'r') as f:
    cpu_stats = f.readline().split()
    idle_prev = int(cpu_stats[4])
    nidle_prev = sum(map(int, cpu_stats[1:4]))

  time.sleep(2)

  with open('/proc/stat', 'r') as f:
    cpu_stats = f.readline().split()

  idle_now = int(cpu_stats[4])
  nidle_now = sum(map(int, cpu_stats[1:4]))

  total_prev = idle_prev + nidle_prev
  total_now = idle_now + nidle_now

  totaldiff = total_now - total_prev
  idlediff = idle_now - idle_prev

  usage = int(100 * (totaldiff - idlediff) / (totaldiff + 1))
  return usage

def get_mem_usage():
  with open('/proc/meminfo', 'r') as f:
    meminfo = f.readlines()

  total = int(meminfo[0].split()[1])
  free = int(meminfo[2].split()[1])
  usage = int((total - free) * 100 / total)
  return usage

def get_mem_used():
  with open('/proc/meminfo', 'r') as f:
    meminfo = f.readlines()

  total = int(meminfo[0].split()[1])
  free = int(meminfo[2].split()[1])
  usage = int((total - free))
  return usage


def get_cpu_temp():
  output = subprocess.check_output(['sensors']).decode('utf-8')
  temp_line = output.strip().split('\n')[-1]    # 最後のtemp1の行を取得
  temp_str = re.split("[:°C\\+]", temp_line)[2] # 温度の文字列部分を抽出
  cpu_temp = float(temp_str) # floatに変換
  return cpu_temp

def get_free_space():
  command = f"df -B1G {record_dir}"
  output = subprocess.check_output(command, shell=True).decode().splitlines()
  free_space = output[-1].split()[3]
  free_space = ''.join(filter(str.isdigit, free_space))
  return free_space


def get_recording_total(url):
  endpoint = '/api/recording'
  params = {'offset': 0, 'limit': 24, 'isHalfWidth': True}
  headers = {'accept': 'application/json'}
  response = requests.get(url + endpoint, params=params, headers=headers)
  data = json.loads(response.text)
  recording_total = data['total']
  return recording_total

def get_reserve_count(url):
  endpoint = '/api/reserves/cnts'
  headers = {'accept': 'application/json'}
  response = requests.get(url + endpoint, headers=headers)
  data = json.loads(response.text)
  reserve_count = data['normal']
  return reserve_count

def get_encoding_current(url):
  endpoint = '/api/encode'
  params = { 'isHalfWidth': True}
  headers = {'accept': 'application/json'}
  response = requests.get(url + endpoint, params=params, headers=headers)
  data = json.loads(response.text)
  items = data['runningItems']
  if items is None:
    return 0
  else:
    return int(len(items))

def get_tuners_info(mirakurun_url):
    endpoint= '/api/tuners'
    headers = {'accept': 'application/json'}
    response = requests.get(mirakurun_url + endpoint, headers=headers)
    data = json.loads(response.text)

    tuners = []
    if data is not None:
        for tuner in data:
            device_name = tuner['name']
            status = 0 if tuner['isFree'] == True else -1
            users = tuner['users']
            if status < 0:
                if tuner['isAvailable'] == False:
                  status = -1 ## Warn:
                elif tuner['isFault'] == True:
                  status = -2 ## Critical(need restart)
                elif users:
                    priority = max([x['priority'] for x in users ])
                    status = 1 if priority < 0 else 2  ## '2'の場合にはチューナーがユーザーによって使用中.

            if tuner['isFree'] == False and tuner['isAvailable'] == False and tuner['isUsing'] == False and tuner['isFault'] == False:
              status = -2  ## 全てのステータスがFalseになる異常ケースがあり、回復不可能なためCritical.
            
            tuners.append( { 'device_name': device_name, 'status': status } )
        return tuners
    else:
        return None


## マシン情報を送信
def send_machine_stat():
  client = InfluxDBClient(url=url, token=token, org=orgs)
  write = client.write_api(write_options=SYNCHRONOUS)
  data = {
    "measurement": "machine",
    "fields" : {
      "cpu_usage": float(get_cpu_usage()),
      "cpu_temp" : float(get_cpu_temp()),
      "mem_usage": int(get_mem_usage()),
      "mem_used" : int(get_mem_used()),
      "free_disk": int(get_free_space()),
    }
  }
  point = Point.from_dict(data)
  write.write(bucket=bucket, record=point)

## EPGStation 情報を送信
def send_epgstation_stat():
  client = InfluxDBClient(url=url, token=token, org=orgs)
  write = client.write_api(write_options=SYNCHRONOUS)
  data = {
    "measurement": "epgstation",
    "fields" : {
      "recording": int(get_recording_total(epgstation_url)),
      "reserve" : int(get_reserve_count(epgstation_url)),
      "encoding": int(get_encoding_current(epgstation_url)),
    }
  }
  point = Point.from_dict(data)
  write.write(bucket=bucket, record=point)

## チューナーデバイス状態を送信
def send_tuner_devinfo():
  tuners = get_tuners_info(mirakurun_url)
  if tuners is None:
    return
  client = InfluxDBClient(url=url, token=token, org=orgs)
  write = client.write_api(write_options=SYNCHRONOUS)
  for tuner in tuners:
    data = {
      "measurement" : "tunerstate",
      "tags" : {
        "device": tuner['device_name']
      },
      "fields": {
        "status": tuner["status"]
      }
    }
    point = Point.from_dict(data)
    write.write(bucket=bucket, record=point)


## Starting...
#print("CPU Usage:" + str(get_cpu_usage()))
#print("CPU Temp :" + str(get_cpu_temp() ))
#print("FreeSpace:" + str(get_free_space()))
#print("Memory   :" + str(get_mem_usage()))
#print("Recoding :" + str(get_recording_total(epgstation_url)))
#print("Reserve  :" + str(get_reserve_count(epgstation_url)))
while True:
  try:
    send_machine_stat()
    send_epgstation_stat()
    send_tuner_devinfo()
  except Exception as e:
    print(str(e))

  time.sleep(60)
