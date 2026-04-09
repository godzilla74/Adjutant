#!/usr/bin/env bash
set -e

ADJUTANT_DIR="$HOME/adjutant"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

echo ""
echo -e "${YELLOW}╔════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║    Adjutant Uninstaller            ║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════╝${NC}"
echo ""

# Confirm
read -p "Type 'uninstall' to confirm removal: " CONFIRM
if [ "$CONFIRM" != "uninstall" ]; then
    echo "Uninstall cancelled."
    exit 0
fi

# Data retention prompt
echo ""
read -p "Delete your configuration and data (DB, logs, credentials)? [y/N]: " DEL_DATA
DEL_DATA="${DEL_DATA:-n}"

# Detect OS
OS="$(uname -s)"
case "${OS}" in
    Darwin*)
        PLATFORM="mac"
        PLIST="$HOME/Library/LaunchAgents/ai.adjutantapp.plist"
        CONFIG_DIR="$HOME/Library/Application Support/Adjutant"
        ;;
    Linux*)
        PLATFORM="linux"
        SERVICE_FILE="$HOME/.config/systemd/user/adjutant.service"
        CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/Adjutant"
        ;;
    *)
        echo -e "${RED}Unsupported OS: ${OS}${NC}"
        exit 1
        ;;
esac

# Stop and remove service
echo "Stopping Adjutant..."
if [ "$PLATFORM" = "mac" ]; then
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
else
    systemctl --user stop adjutant 2>/dev/null || true
    systemctl --user disable adjutant 2>/dev/null || true
    rm -f "$SERVICE_FILE"
    systemctl --user daemon-reload 2>/dev/null || true
fi
echo -e "${GREEN}✓ Service removed${NC}"

# Remove config/data
if [[ "$DEL_DATA" =~ ^[Yy]$ ]]; then
    rm -rf "$CONFIG_DIR"
    echo -e "${GREEN}✓ Configuration and data deleted${NC}"
else
    echo -e "${BLUE}  Configuration kept at: $CONFIG_DIR${NC}"
fi

# Remove install directory
if [ -d "$ADJUTANT_DIR" ]; then
    rm -rf "$ADJUTANT_DIR"
    echo -e "${GREEN}✓ Install directory removed${NC}"
fi

# Remove CLI symlink
rm -f "$HOME/.local/bin/adjutant"
echo -e "${GREEN}✓ CLI removed${NC}"

# Clean up PATH addition from shell rc
for RC in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.bash_profile"; do
    if [ -f "$RC" ]; then
        # Remove the line we added during install (portable sed -i)
        sed -i.bak '/export PATH="\$HOME\/.local\/bin:\$PATH"/d' "$RC" 2>/dev/null && \
            rm -f "${RC}.bak" || true
    fi
done

echo ""
echo -e "${GREEN}Adjutant has been uninstalled.${NC}"
echo ""
