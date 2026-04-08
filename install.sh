#!/usr/bin/env bash
set -e

ADJUTANT_DIR="$HOME/adjutant"
REPO_URL="https://github.com/jtaventures/adjutant.git"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

echo ""
echo -e "${BLUE}╔════════════════════════════════════╗${NC}"
echo -e "${BLUE}║    Welcome to Adjutant Installer   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════╝${NC}"
echo ""

# Detect OS
OS="$(uname -s)"
case "${OS}" in
    Darwin*) PLATFORM="mac" ;;
    Linux*)  PLATFORM="linux" ;;
    *) echo -e "${RED}Unsupported OS: ${OS}${NC}"; exit 1 ;;
esac

# Check/install Python 3.12+
PYTHON=""
check_python() {
    if command -v python3 >/dev/null 2>&1; then
        MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
        MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 12 ]; then
            PYTHON="python3"; return 0
        fi
    fi
    if command -v python3.12 >/dev/null 2>&1; then
        PYTHON="python3.12"; return 0
    fi
    return 1
}

if check_python; then
    echo -e "${GREEN}✓ Python $(python3 --version 2>&1 | cut -d' ' -f2)${NC}"
else
    echo "Python 3.12+ not found. Installing..."
    if [ "$PLATFORM" = "mac" ]; then
        if ! command -v brew >/dev/null 2>&1; then
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        brew install python@3.12
        PYTHON="python3.12"
    else
        sudo apt-get update -qq
        sudo apt-get install -y python3.12 python3.12-venv python3.12-dev
        PYTHON="python3.12"
    fi
fi

# Check/install Node 18+
if command -v node >/dev/null 2>&1 && [ "$(node -e 'console.log(process.version.slice(1).split(".")[0])')" -ge 18 ]; then
    echo -e "${GREEN}✓ Node.js $(node --version)${NC}"
else
    echo "Node.js 18+ not found. Installing..."
    if [ "$PLATFORM" = "mac" ]; then
        brew install node
    else
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt-get install -y nodejs
    fi
fi

# Check/install git
if ! command -v git >/dev/null 2>&1; then
    [ "$PLATFORM" = "mac" ] && brew install git || sudo apt-get install -y git
fi
echo -e "${GREEN}✓ git$(git --version | sed 's/git version//')${NC}"

# Check if already installed
if [ -d "$ADJUTANT_DIR" ]; then
    echo -e "${YELLOW}Adjutant is already installed at $ADJUTANT_DIR${NC}"
    echo "Run 'adjutant update' to update to the latest version."
    exit 0
fi

# Clone repo
echo "Downloading Adjutant..."
git clone --quiet "$REPO_URL" "$ADJUTANT_DIR"

# Python venv + deps
echo "Installing Python dependencies..."
$PYTHON -m venv "$ADJUTANT_DIR/.venv"
"$ADJUTANT_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$ADJUTANT_DIR/.venv/bin/pip" install --quiet -r "$ADJUTANT_DIR/requirements.txt"

# Node deps
echo "Installing UI dependencies..."
cd "$ADJUTANT_DIR/ui" && npm install --silent && cd "$ADJUTANT_DIR"

# Config directory
if [ "$PLATFORM" = "mac" ]; then
    CONFIG_DIR="$HOME/Library/Application Support/Adjutant"
else
    CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/Adjutant"
fi
mkdir -p "$CONFIG_DIR"
CONFIG_FILE="$CONFIG_DIR/config.env"
DB_FILE="$CONFIG_DIR/adjutant.db"

# Setup prompts
echo ""
echo -e "${YELLOW}Let's set up your Adjutant.${NC}"
echo ""

read -p "What would you like to name your AI assistant? [Hannah]: " AGENT_NAME
AGENT_NAME="${AGENT_NAME:-Hannah}"

while true; do
    read -s -p "Choose a password to protect your Adjutant: " AGENT_PASSWORD; echo ""
    read -s -p "Confirm password: " AGENT_PASSWORD2; echo ""
    [ "$AGENT_PASSWORD" = "$AGENT_PASSWORD2" ] && break
    echo -e "${RED}Passwords don't match. Try again.${NC}"
done

while true; do
    read -p "Your Anthropic API key (from console.anthropic.com): " ANTHROPIC_API_KEY
    echo -n "Testing your API key..."
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "x-api-key: $ANTHROPIC_API_KEY" \
        -H "anthropic-version: 2023-06-01" \
        "https://api.anthropic.com/v1/models")
    if [ "$HTTP_STATUS" = "200" ]; then
        echo -e " ${GREEN}✓${NC}"; break
    else
        echo -e " ${RED}That key doesn't seem to work — double-check and try again.${NC}"
    fi
done

echo ""
echo "Now let's help $AGENT_NAME get to know you."
read -p "  Your name: " AGENT_OWNER_NAME
echo "  Tell $AGENT_NAME about yourself and your business"
echo "  (role, industry, goals — the more they know, the more useful they'll be):"
read -p "  > " AGENT_OWNER_BIO

echo ""
echo "Let's add your first product."
read -p "  Business name: " PRODUCT_NAME
read -p "  What does it do? (one sentence): " PRODUCT_DESC
PRODUCT_ID=$(echo "$PRODUCT_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd '[:alnum:]-')

# Write config
cat > "$CONFIG_FILE" << ENVEOF
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
AGENT_PASSWORD=$AGENT_PASSWORD
AGENT_NAME=$AGENT_NAME
AGENT_OWNER_NAME=$AGENT_OWNER_NAME
AGENT_OWNER_BIO=$AGENT_OWNER_BIO
ADJUTANT_SEED_PRODUCT_ID=$PRODUCT_ID
ADJUTANT_SEED_PRODUCT_NAME=$PRODUCT_NAME
ADJUTANT_SEED_PRODUCT_DESC=$PRODUCT_DESC
AGENT_DB=$DB_FILE
ENVEOF
chmod 600 "$CONFIG_FILE"

# Build UI
echo "Building the interface..."
cd "$ADJUTANT_DIR/ui" && npm run build --silent && cd "$ADJUTANT_DIR"

# Register service
if [ "$PLATFORM" = "mac" ]; then
    PLIST="$HOME/Library/LaunchAgents/ai.adjutantapp.plist"
    cat > "$PLIST" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>ai.adjutantapp</string>
    <key>ProgramArguments</key>
    <array>
        <string>$ADJUTANT_DIR/.venv/bin/uvicorn</string>
        <string>backend.main:app</string>
        <string>--host</string><string>0.0.0.0</string>
        <string>--port</string><string>8001</string>
    </array>
    <key>WorkingDirectory</key><string>$ADJUTANT_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>ADJUTANT_CONFIG</key><string>$CONFIG_FILE</string>
    </dict>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>$CONFIG_DIR/adjutant.log</string>
    <key>StandardErrorPath</key><string>$CONFIG_DIR/adjutant.log</string>
</dict>
</plist>
PLISTEOF
    launchctl load "$PLIST"
else
    mkdir -p "$HOME/.config/systemd/user"
    cat > "$HOME/.config/systemd/user/adjutant.service" << SVCEOF
[Unit]
Description=Adjutant AI Executive Assistant
After=network.target

[Service]
Type=simple
WorkingDirectory=$ADJUTANT_DIR
Environment=ADJUTANT_CONFIG=$CONFIG_FILE
ExecStart=$ADJUTANT_DIR/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8001
Restart=on-failure
RestartSec=3
StandardOutput=append:$CONFIG_DIR/adjutant.log
StandardError=append:$CONFIG_DIR/adjutant.log

[Install]
WantedBy=default.target
SVCEOF
    systemctl --user daemon-reload
    systemctl --user enable adjutant
    systemctl --user start adjutant
fi

# Install CLI symlink
mkdir -p "$HOME/.local/bin"
chmod +x "$ADJUTANT_DIR/bin/adjutant"
ln -sf "$ADJUTANT_DIR/bin/adjutant" "$HOME/.local/bin/adjutant"

# Add ~/.local/bin to PATH if not already there
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    SHELL_RC="$HOME/.bashrc"
    [ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
    export PATH="$HOME/.local/bin:$PATH"
fi

# Done
echo ""
echo -e "${GREEN}╔════════════════════════════════════╗${NC}"
echo -e "${GREEN}║    Adjutant is running! 🎉         ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════╝${NC}"
echo ""
echo -e "  Open: ${BLUE}http://localhost:8001${NC}"
echo -e "  Manage: ${YELLOW}adjutant {start|stop|restart|update|logs|uninstall}${NC}"
echo ""

sleep 2
[ "$PLATFORM" = "mac" ] && open "http://localhost:8001" || (xdg-open "http://localhost:8001" 2>/dev/null || true)
