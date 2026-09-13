---
name: ipo-deploy-update
description: >-
  Package and prepare clean, production-safe deployment zip archives for the IPO Wise bot on the Google Cloud VM.
  Use this skill whenever the user asks for a zip file, asks to package or deploy changes, asks what files to copy to the VM,
  or asks how to upload and restart the bot in production.
---

# IPO-Wise VM Deployment & Packaging Skill

This skill guides the agent in packaging updates for the **IPO-Wise Telegram Alert Bot** to be deployed to the **Google Cloud VM**.

## 1. Hosting Architecture Overview

Understanding the environment differences prevents common deployment bugs:
* **Local Workspace:** `/Users/kurieneapen/Projects/IPO-Wise/ipo-alert-bot`
  * Runs via `python3 main.py` at root `http://localhost:5050/`.
* **Google Cloud VM:**
  * Destination Path: `/home/kurieneapenk_dev/ipo-alert-bot/`
  * Process Manager: **PM2** (`pm2 restart ipo-wise-bot`)
  * Service Name: `ipo-wise-bot`
  * Subpath: `BASE_PATH: "/ipo"` (served via Nginx reverse proxy at `http://<VM-IP>/ipo/`)
  * Port & Host: `HOST: "127.0.0.1"`, `PORT: 5050` (internal only; external traffic must go through Nginx port 80/443).

## 2. Critical Safety Rules

1. **NEVER overwrite `ipo_bot.db`:**
   * The VM's `ipo_bot.db` contains active Telegram subscriber registrations, approval statuses, mute lists, and historical alert dispatch records.
   * `ipo_bot.db*` **MUST ALWAYS BE EXCLUDED** when creating zip packages.
2. **Always validate syntax before zipping:**
   * Run `python3 -m py_compile` across all Python files.
   * Run `node -c` on any modified `.js` files.
3. **Bump cache-busters on UI changes:**
   * If `web/static/style.css`, `app.js`, or `settings.js` were modified, bump the cache-buster query parameter (e.g. `?v=3.6`) in `web/templates/*.html` so browsers don't serve stale cached assets.
4. **Use incremented zip names (e.g., `ipo-bot-v3.6.zip`):**
   * GCP's Browser SSH file upload utility may skip or auto-rename duplicate files if uploaded with the same filename. Using an incremented version guarantees clean uploads.

## 3. Step-by-Step Packaging Procedure

### Step 1: Run Pre-Flight Validation
Execute Python and JavaScript syntax checks:
```bash
python3 -m py_compile main.py config.py database.py bot/*.py scraper/*.py scheduler/*.py web/*.py
node -c web/static/*.js
```

### Step 2: Run the Automated Packager Script
From the workspace root, run the bundled packaging script:
```bash
bash .agents/skills/ipo-deploy-update/scripts/package_update.sh
```
*(Or specify an explicit version: `bash .agents/skills/ipo-deploy-update/scripts/package_update.sh 3.6`)*

Alternatively, if running the command manually from `ipo-alert-bot`:
```bash
zip -q -r ../ipo-bot-v3.6.zip . \
  -x "ipo_bot.db*" \
  -x "*.pyc" \
  -x "*__pycache__*" \
  -x "*.DS_Store" \
  -x "*/.DS_Store" \
  -x ".git*" \
  -x "*/.git*" \
  -x "venv*" \
  -x "*.log"
cp ../ipo-bot-v3.6.zip ../ipo-alert-bot-update.zip
```

### Step 3: Provide Response & VM Instructions
Always provide the user with:
1. Clickable file link to the generated zip file: `[ipo-bot-vX.Y.zip](file:///Users/kurieneapen/Projects/IPO-Wise/ipo-bot-vX.Y.zip)`
2. Summary of changes packaged in this version.
3. Exact, copy-paste commands for their VM terminal:

```bash
# 1. Unzip over the existing folder (preserves ipo_bot.db):
unzip -o ~/ipo-bot-vX.Y.zip -d /home/kurieneapenk_dev/ipo-alert-bot/

# 2. Restart the PM2 process:
pm2 restart ipo-wise-bot

# 3. Check logs to confirm clean startup:
pm2 logs ipo-wise-bot --lines 20 --nostream
```
