#!/bin/bash
set -e

sudo apt install python3-pip lm-sensors
pip3 install influxdb-client requests

## chktspkt
pushd .
git clone --depth 1 https://github.com/techmadot/chktspkt.git /tmp/chktspkt
cd /tmp/chktspkt
make && sudo make install
popd 

## 実行ユーザーの置換.
sed -i -e "s/MYUSER/$USER/" recbox-monitor.service
chmod +x recbox-monitor.service

## スクリプトを配置.
sudo mkdir -p /opt/monitor
sudo cp ./monitor.py  /opt/monitor/
sudo cp ./check_tsfile.py  /opt/monitor/
sudo cp ./recbox-monitor.service /etc/systemd/system/

## systemctl でセット.
sudo systemctl daemon-reload
sudo systemctl enable recbox-monitor.service
sudo systemctl start recbox-monitor.service

## EPGStation の設定を変更
if [ -e $HOME/EPGStation/config/config.yml ]; then
  echo "Found EPGStation config."
  FINISH_CMD="recordingFinishCommand: '/usr/bin/python  /opt/monitor/check_tsfile.py'"
  echo $FINISH_CMD >> $HOME/EPGStation/config/config.yml
fi

