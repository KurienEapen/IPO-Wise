#!/usr/bin/env bash
# ==============================================================================
# IPO-Wise Deployment Packager
# Packages clean update archives for deployment to the Google Cloud VM
# ==============================================================================
set -e

# Resolve workspace and bot directory dynamically
CURR="$(pwd)"
if [ -d "$CURR/ipo-alert-bot" ]; then
  WORKSPACE_ROOT="$CURR"
  BOT_DIR="$CURR/ipo-alert-bot"
elif [ -f "$CURR/main.py" ] && [ -d "$CURR/web" ]; then
  BOT_DIR="$CURR"
  WORKSPACE_ROOT="$(cd "$CURR/.." && pwd)"
else
  # Walk up from script directory
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
  BOT_DIR="$WORKSPACE_ROOT/ipo-alert-bot"
fi

if [ ! -d "$BOT_DIR" ]; then
  echo "❌ Error: Could not find ipo-alert-bot at $BOT_DIR"
  exit 1
fi

echo "🔍 Validating codebase syntax..."

# 1. Python compilation check
python3 -m py_compile \
  "$BOT_DIR/main.py" \
  "$BOT_DIR/config.py" \
  "$BOT_DIR/database.py" \
  "$BOT_DIR/bot/"*.py \
  "$BOT_DIR/scraper/"*.py \
  "$BOT_DIR/scheduler/"*.py \
  "$BOT_DIR/web/"*.py
echo "✅ Python syntax verified."

# 2. JavaScript check (if node available)
if command -v node >/dev/null 2>&1; then
  for js in "$BOT_DIR/web/static/"*.js; do
    if [ -f "$js" ]; then
      node -c "$js"
    fi
  done
  echo "✅ JavaScript syntax verified."
fi

# 3. Determine next version number
LATEST_VER=0
for f in "$WORKSPACE_ROOT"/ipo-bot-v*.zip; do
  if [ -f "$f" ]; then
    v=$(basename "$f" | sed -E 's/ipo-bot-v([0-9.]+)\.zip/\1/')
    # Basic numeric comparison for x.y
    if [ -n "$v" ]; then
      LATEST_VER="$v"
    fi
  fi
done

# If argument supplied, use that version, else calculate or default to 3.6
if [ -n "$1" ]; then
  VERSION="$1"
elif [ -n "$LATEST_VER" ] && [ "$LATEST_VER" != "0" ]; then
  MAJOR=$(echo "$LATEST_VER" | cut -d. -f1)
  MINOR=$(echo "$LATEST_VER" | cut -d. -f2)
  NEXT_MINOR=$((MINOR + 1))
  VERSION="${MAJOR}.${NEXT_MINOR}"
else
  VERSION="3.6"
fi

ZIP_NAME="ipo-bot-v${VERSION}.zip"
TARGET_ZIP="$WORKSPACE_ROOT/$ZIP_NAME"
UPDATE_ZIP="$WORKSPACE_ROOT/ipo-alert-bot-update.zip"
STANDARD_ZIP="$WORKSPACE_ROOT/ipo-alert-bot.zip"

echo "📦 Packaging clean update as: $ZIP_NAME..."

# 4. Create zip archive from inside ipo-alert-bot directory
cd "$BOT_DIR"
rm -f "$TARGET_ZIP" "$UPDATE_ZIP" "$STANDARD_ZIP"

zip -q -r "$TARGET_ZIP" . \
  -x "ipo_bot.db*" \
  -x "*.pyc" \
  -x "*__pycache__*" \
  -x "*.DS_Store" \
  -x "*/.DS_Store" \
  -x ".git*" \
  -x "*/.git*" \
  -x "venv*" \
  -x "*/venv*" \
  -x "*.log" \
  -x "*/.pytest_cache*"

# Mirror to generic update zips
cp "$TARGET_ZIP" "$UPDATE_ZIP"
cp "$TARGET_ZIP" "$STANDARD_ZIP"

ZIP_SIZE=$(ls -lh "$TARGET_ZIP" | awk '{print $5}')

echo ""
echo "================================================================="
echo "🎉 Package Ready: $ZIP_NAME ($ZIP_SIZE)"
echo "   Path: $TARGET_ZIP"
echo "================================================================="
echo ""
echo "📋 GCP VM Deployment Instructions:"
echo "1. In your GCP Browser SSH window, click the Gear Icon ⚙️ -> 'Upload file'."
echo "2. Upload: $ZIP_NAME (or ipo-alert-bot-update.zip)"
echo "3. Run these commands in the VM terminal:"
echo ""
echo "   unzip -o ~/$ZIP_NAME -d /home/kurieneapenk_dev/ipo-alert-bot/"
echo "   pm2 restart ipo-wise-bot"
echo "   pm2 logs ipo-wise-bot --lines 20 --nostream"
echo ""
echo "🔒 Note: ipo_bot.db was excluded. Your live database and subscribers are safe."
