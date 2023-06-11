#!/bin/bash
## Usage setup.sh (exec-user)

if [ -z $1 ]; then
  echo "Usage: $0 (username)"
  exit 1
fi

sudo apt install python3-pip lm-sensors
pip3 install influxdb-client requests

## 実行ユーザーの置換.
sed -i -e "s/MYUSER/$1/" recbox-monitor.service
chmod +x recbox-monitor.service

## スクリプトを配置.
sudo mkdir -p /opt/monitor
sudo cp ./monitor.py  /opt/monitor/
sudo cp ./recbox-monitor.service /etc/systemd/system/

## systemctl でセット.
sudo systemctl daemon-reload
sudo systemctl enable recbox-monitor.service
sudo systemctl start recbox-monitor.service
