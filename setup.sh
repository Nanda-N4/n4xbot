#!/bin/bash
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}🚀 N4XBOT Setup စတင်နေပါပြီ...${NC}"
sudo apt update && sudo apt install -y python3-pip python3-venv git
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
mkdir -p backups assets

CURRENT_DIR=$(pwd)
USER_NAME=$(whoami)

sudo bash -c "cat > /etc/systemd/system/n4xbot.service <<EOF
[Unit]
Description=N4XBOT Service
After=network.target

[Service]
User=$USER_NAME
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/venv/bin/python3 $CURRENT_DIR/main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl enable n4xbot
sudo systemctl start n4xbot
echo -e "${GREEN}✅ တပ်ဆင်မှု ပြီးဆုံးပါပြီ။${NC}"
