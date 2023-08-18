import time
import subprocess
import re
import requests
import json
import sys, os
import logging, atexit
from datetime import datetime
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

DEBUG_MODE = os.environ.get('DEBUG_MODE', '0') == '1'

logger = logging.getLogger('check_tsfile')
logging.basicConfig( level = logging.DEBUG if DEBUG_MODE else logging.CRITICAL)
fh = logging.FileHandler('/tmp/check_tsfile.log')
logger.addHandler(fh)
atexit.register(fh.close)


infile = os.getenv('RECPATH', default=None)
basetime = os.getenv('STARTAT', default=0)
channel_id = os.getenv('CHANNELID', default=0)
channel_name = os.getenv('CHANNELNAME', 'Unknown')

def check_tspacket():
    global basetime, infile, channel_id
    if infile is None:
        print('File not found')
        return None

    ## EPGStationのUNIXTIMEはミリ秒単位のため、秒単位へ変換.
    basetime = int(int(basetime) / 1000)

    cmd = ['/usr/local/bin/chktspkt', '-j', '-b', str(basetime), '-m', str(infile) ]
    print(str(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return json.loads(result.stdout)
    else:
        print(result.stdout)
        print('failed.')
        return None

def send_tsinfo(data):
    global basetime, infile, channel_name, channel_id

    client = InfluxDBClient(url=url, token=token, org=orgs)
    write = client.write_api(write_options=SYNCHRONOUS)
    count = 0
    for v in data['timebased_log']:
        dt = datetime.fromisoformat(v['timestamp'])

        point = {
            "measurement" : "tsfile_status",
            "time" : (int)(dt.timestamp()) * 1000000000, ## ナノ秒単位にしないと受け付けないため.
            "fields" : {
                "error" : v["error"],
                "drop" : v["drop"],
                "scramble" : v["scramble"],
                "channel" : int(channel_id),
            }
        }
        write.write(bucket=bucket, record=point)
    
    summary = data['summary']
    if summary:
        
        point = {
            "measurement" : "tsfile_info",
            "time" : int(basetime) * 1000000,  # ms -> ns
            "fields": {
                "drop" : int(summary['drop']),
                "error" : int(summary['error']),
                "scramble" : int(summary['scramble']),
                "channel": str(channel_name).strip()
            }
        }
        write.write(bucket=bucket, record=point)


if __name__ == '__main__':
    try:
        logger.debug(f'[{str(datetime.now())}] start: {infile}')
        logger.debug(f'  base={basetime}, channel_name={channel_name}, channel_id={channel_id}')

        json_data = check_tspacket()
        if json_data is None:
            logger.critical(f'[{str(datetime.now())}] failed json data. {infile}')
            sys.exit(-1)

        send_tsinfo(json_data)
        logger.debug(f'  {json_data}')
        logger.debug(f'[{str(datetime.now())}] send finished: {infile}')

    except Exception as ex:
        logger.critical(f'[{str(datetime.now())}] {str(ex)}')
        
