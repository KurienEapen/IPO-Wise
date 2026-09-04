# IPO Wise: Telegram Alert Bot & Web Console

An intelligent, lightweight service that tracks Indian Mainboard and SME IPOs, filters for high GMP (> 15%), and delivers clean alert cards directly to a Telegram chat or channel. It features a modern dark-mode Web Management Console and interactive mute controls.

---

## 🌟 Key Features

* **InvestorGain v2 Live Feed:** Directly parses official `cloud/v2/report/data-read/` endpoints for real-time GMP (Report 331) and Subscription Demand (Report 333).
* **Smart Filtering:** Automatically alerts only on **OPEN** IPOs meeting your configured GMP threshold (default > 15%).
* **Complete Investment Breakdown:**
  * IPO Name & Category (Mainboard vs SME)
  * Start Date & End Date
  * GMP (₹ amount and % gain)
  * Subscription Multipliers: Overall, Retail, HNI (sNII/bNII), QIB
  * Minimum Order Quantities:
    * **Retail:** 1 Lot (shares and min ₹ amount)
    * **HNI:** Minimum lot count required to exceed ₹2,00,000 application limit
* **Interactive Telegram Actions:**
  * **Inline Buttons:** Each alert includes `[ ✅ Applied (Mute) ]` and `[ 🔕 Ignore IPO ]` buttons. Tapping either silences further notifications for that specific IPO.
  * **Bot Commands:** `/check`, `/applied <Name>`, `/ignore <Name>`, `/unmute <Name>`, `/muted`, `/status`.
  * **Channel Support:** Can be added as an administrator to Telegram channels to broadcast alerts to all members.
* **Modern Web Console:**
  * Master Enable/Disable switch
  * Bot Token & Chat ID configuration + "Test Connection" button
  * GMP threshold slider (0–60%)
  * Scheduled run times (default: `10:00, 12:30, 15:30` IST)
  * "⚡ Check Now" instant trigger
  * Live IPO explorer table and 1-click Unmute management
* **Google Cloud VM Ready:** Pre-configured `systemd` service and `docker-compose.yml` for 24/7 background operation.

---

## 🚀 Quick Start (Local)

### 1. Install Dependencies
```bash
cd ipo-alert-bot
pip3 install -r requirements.txt
```

### 2. Run Application
```bash
python3 main.py
```
Visit the Web Console in your browser:
**`http://localhost:8080`**

### 🔐 Console Authentication
To prevent unauthorized access when deployed on a public IP or Cloud VM, the console is protected by an admin password:
* **Default Password:** `admin123`
* **Custom Environment Variable:** Set `ADMIN_PASSWORD=your_custom_password` before starting the server.
* **Updating Password:** You can also update the admin password directly from the **"Admin Security"** box on the dashboard once logged in.
* **Logout:** Click the **"🔒 Logout"** button in the top-right header at any time.

---

## 🤖 Telegram Bot Configuration

### Step 1: Create a Bot
1. Open Telegram and search for **`@BotFather`**.
2. Send `/newbot` and follow the prompts to get your **Bot Token** (e.g. `123456789:ABCdefGhI...`).

### Step 2: Get Your Chat ID or Channel ID
* **For Personal Alerts:**
  1. Start a conversation with your bot by clicking `/start`.
  2. Send a message to **`@userinfobot`** to discover your numeric Chat ID (e.g. `987654321`).
* **For Channel Alerts:**
  1. Create a Telegram Channel.
  2. Add your bot as an **Administrator** with "Post Messages" permission.
  3. Use the public channel username (e.g. `@MyIPOAlerts`) or numeric channel ID (e.g. `-100192837465`).

### Step 3: Configure via Web Console
1. Open `http://localhost:8080`.
2. Enter your **Bot Token** and **Target Chat / Channel ID**.
3. Click **"📡 Test Telegram Connection"** to verify that your bot can send messages.
4. Click **"💾 Save Settings"**.

---

## ☁️ Google Cloud VM Deployment (24/7 Free Tier)

### 1. Create a VM on GCP
1. In Google Cloud Console, create a Compute Engine VM instance:
   * **Machine type:** `e2-micro` (Eligible for GCP Always Free Tier).
   * **OS:** Ubuntu 22.04 LTS or Debian 11.
   * **Firewall:** Check "Allow HTTP traffic".
2. Create a VPC firewall rule to allow port `8080` (or use reverse proxy like Nginx on port 80/443):
   * Protocol: TCP, Port: `8080`.

### 2. Setup the Code on the VM
SSH into your VM and run:
```bash
# Update system
sudo apt-get update && sudo apt-get install -y python3 python3-pip git

# Clone or copy the repo
git clone <your-repo-url> /opt/ipo-alert-bot
cd /opt/ipo-alert-bot/ipo-alert-bot

# Install requirements
pip3 install -r requirements.txt
```

### 3. Setup Systemd Service (Auto-Start on Boot)
```bash
# Copy service file
sudo cp deploy/ipo-bot.service /etc/systemd/system/ipo-bot.service

# Reload and enable service
sudo systemctl daemon-reload
sudo systemctl enable ipo-bot
sudo systemctl start ipo-bot

# Check status
sudo systemctl status ipo-bot
```

Your bot and Web Console will now run 24/7 on the VM and restart automatically if the machine reboots. Access the console at `http://<VM-EXTERNAL-IP>:8080`.
