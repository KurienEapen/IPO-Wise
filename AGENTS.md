# IPO-Wise Agent Instructions & Runbook

## Project Overview
This repository contains **IPO-Wise**, an automated Telegram alert bot, web scraper, and management console for Indian IPOs (Mainboard & SME) with Grey Market Premium (GMP) tracking, 1-tap broker bidding bridges, and subscriber approvals.

* **Primary Codebase:** `./ipo-alert-bot/`
* **Local Run Command:** `python3 main.py` (runs at `http://localhost:5050/`)

---

## Production Hosting (Google Cloud VM)
* **VM Directory:** `/home/kurieneapenk_dev/ipo-alert-bot/`
* **PM2 Process Name:** `ipo-wise-bot`
* **Subpath Routing:** `BASE_PATH: "/ipo"` (accessible via Nginx reverse proxy at `http://<VM-IP>/ipo/`)
* **Binding:** `HOST: "127.0.0.1"`, `PORT: 5050` (internal loopback; only accessible externally via Nginx port 80/443)

---

## Deployment & Packaging Instructions

Whenever the user asks:
* *"Give me a zip file I can upload"*
* *"Package the changes for the VM"*
* *"How do I deploy this to my server?"*

### Rules:
1. **Never include `ipo_bot.db` in zip files.** The production database stores subscriber registrations, approval statuses, and mute lists that must be preserved.
2. **Pre-flight Syntax Validation:** Always run `python3 -m py_compile` and `node -c web/static/*.js`.
3. **Cache-busting:** If `style.css`, `app.js`, or `settings.js` were modified, ensure the query string version (e.g. `?v=X.Y`) is updated in `web/templates/*.html`.
4. **Automated Packaging:** Run the packaging script:
   ```bash
   bash .agents/skills/ipo-deploy-update/scripts/package_update.sh
   ```
   Or activate the **`ipo-deploy-update`** skill.
5. **Always provide exact VM commands in your response:**
   ```bash
   unzip -o ~/ipo-bot-vX.Y.zip -d /home/kurieneapenk_dev/ipo-alert-bot/
   pm2 restart ipo-wise-bot
   pm2 logs ipo-wise-bot --lines 20 --nostream
   ```
