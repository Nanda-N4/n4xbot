## Installation

### 
```bash
mkdir -p n4xbot && cd n4xbot && git clone https://github.com/Nanda-N4/n4xbot.git . && chmod +x setup.sh && ./setup.sh
```

Paste the following content (replace with your actual values):
BOT_TOKEN=xxxx
ADMIN_ID=xxx
ADMIN_LINK=xxx

(Press Ctrl+O, Enter, and Ctrl+X to save and exit)

### Step 3: Run the Setup Script
chmod +x setup.sh
./setup.sh

## Bot Management

* Check Bot Status: sudo systemctl status n4xbot
* Restart Bot: sudo systemctl restart n4xbot
* Stop Bot: sudo systemctl stop n4xbot
* View Error Logs: journalctl -u n4xbot -f

## Project Structure
* backups/: Location of automated daily data backups.
* products.json: Database file for product listings.
* settings.json: Database file for bot configurations and payment methods.
* assets/: Directory for storing the welcome banner and other media.

## Important Notes
* Since this is a Public Repository, never commit your .env or .json files.
* The bot automatically sends database backups to the Admin every day at 12:00 AM.

---
Maintained by N4XBOT Project
