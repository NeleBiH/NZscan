#!/bin/bash
set -euo pipefail

# ── Colors ──
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ── Paths ──
APP_NAME="NZscan"
APP_VERSION="0.1-alpha"
INSTALL_DIR="$HOME/.local/share/nzscan"
CONFIG_FILE="$INSTALL_DIR/config.json"
DESKTOP_FILE="$HOME/.local/share/applications/nzscan.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor"
ICON_48="$ICON_DIR/48x48/apps/nzscan.png"
ICON_128="$ICON_DIR/128x128/apps/nzscan.png"
ICON_256="$ICON_DIR/256x256/apps/nzscan.png"
BIN_FILE="$HOME/.local/bin/nzscan"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_FILE="$SCRIPT_DIR/main.py"

# ── Helpers ──
info()  { echo -e "${CYAN}[*]${NC} $1"; }
ok()    { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; }

header() {
    echo ""
    echo -e "${CYAN}${BOLD}╔════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}${BOLD}║       NZscan Setup v${APP_VERSION}          ║${NC}"
    echo -e "${CYAN}${BOLD}║       WiFi Scanner for Linux           ║${NC}"
    echo -e "${CYAN}${BOLD}╚════════════════════════════════════════╝${NC}"
    echo ""
}

# ── Distro detection ──
DISTRO="unknown"
DISTRO_LIKE=""
DISTRO_NAME="Unknown Linux"

detect_distro() {
    if [ -f /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        DISTRO="${ID:-unknown}"
        DISTRO_LIKE="${ID_LIKE:-}"
        DISTRO_NAME="${PRETTY_NAME:-$NAME}"
    elif [ -f /etc/lsb-release ]; then
        # shellcheck disable=SC1091
        . /etc/lsb-release
        DISTRO="${DISTRIB_ID:-unknown}"
        DISTRO_NAME="${DISTRIB_DESCRIPTION:-Unknown}"
    fi
    DISTRO="${DISTRO,,}"   # lowercase
    DISTRO_LIKE="${DISTRO_LIKE,,}"
    info "Detected: ${DISTRO_NAME} (id=${DISTRO})"
}

# Returns the package manager family: apt | dnf | pacman | zypper | xbps | unknown
pkg_family() {
    case "$DISTRO" in
        ubuntu|debian|linuxmint|pop|kali|elementary|zorin|raspbian) echo "apt" ;;
        fedora|rhel|centos|almalinux|rocky|nobara)                  echo "dnf" ;;
        arch|manjaro|endeavouros|cachyos|artix|garuda|blackarch)    echo "pacman" ;;
        opensuse*|sles|tumbleweed|leap)                             echo "zypper" ;;
        void)                                                        echo "xbps" ;;
        *)
            # Fall back to ID_LIKE
            if [[ "$DISTRO_LIKE" == *"arch"* ]];   then echo "pacman"
            elif [[ "$DISTRO_LIKE" == *"debian"* || "$DISTRO_LIKE" == *"ubuntu"* ]]; then echo "apt"
            elif [[ "$DISTRO_LIKE" == *"fedora"* || "$DISTRO_LIKE" == *"rhel"* ]];   then echo "dnf"
            elif [[ "$DISTRO_LIKE" == *"suse"* ]]; then echo "zypper"
            else echo "unknown"
            fi
            ;;
    esac
}

install_system_deps() {
    local family
    family=$(pkg_family)

    info "Installing system dependencies via package manager..."

    case "$family" in
        apt)
            sudo apt-get update -q
            sudo apt-get install -y python3 python3-pip python3-venv \
                network-manager
            ;;
        dnf)
            sudo dnf install -y python3 python3-pip \
                NetworkManager
            ;;
        pacman)
            sudo pacman -Sy --noconfirm --needed python python-pip \
                networkmanager
            ;;
        zypper)
            sudo zypper install -y python3 python3-pip \
                NetworkManager
            ;;
        xbps)
            sudo xbps-install -y python3 python3-pip \
                NetworkManager
            ;;
        unknown)
            warn "Cannot detect package manager for '${DISTRO}'."
            warn "Please install manually: python3, python3-pip, NetworkManager, bluez, rfkill"
            return 1
            ;;
    esac

    ok "System packages installed"
}

install_pyside6() {
    info "Installing PySide6 via pip..."

    # Try pipx / pip depending on PEP 668 (externally managed)
    if python3 -m pip install --user PySide6 2>/dev/null; then
        ok "PySide6 installed (pip --user)"
        return 0
    fi

    # If pip refuses due to externally managed env, try system package
    local family
    family=$(pkg_family)
    case "$family" in
        pacman)  sudo pacman -Sy --noconfirm --needed python-pyside6 && ok "PySide6 installed (pacman)" ;;
        apt)     sudo apt-get install -y python3-pyside6 && ok "PySide6 installed (apt)" ;;
        dnf)     sudo dnf install -y python3-pyside6 && ok "PySide6 installed (dnf)" ;;
        zypper)  sudo zypper install -y python3-pyside6 && ok "PySide6 installed (zypper)" ;;
        *)
            err "Could not install PySide6 automatically."
            err "Try manually: pip install --user PySide6  OR  pip install --break-system-packages PySide6"
            return 1
            ;;
    esac
}

# ── Dependency check (with auto-install option) ──
check_deps() {
    local missing=0

    detect_distro
    echo ""

    # python3
    if ! command -v python3 &>/dev/null; then
        err "python3 not found"
        missing=1
    else
        ok "python3 found: $(python3 --version 2>&1)"
    fi

    # PySide6
    if ! python3 -c "import PySide6" &>/dev/null; then
        err "PySide6 not found"
        missing=1
    else
        ok "PySide6 found"
    fi

    # nmcli (warn only)
    if ! command -v nmcli &>/dev/null; then
        warn "nmcli not found — WiFi scanning won't work"
        missing=2   # soft miss
    else
        ok "nmcli found"
    fi

    if [ "$missing" -eq 0 ]; then
        return 0
    fi

    echo ""

    if [ "$missing" -eq 1 ]; then
        # Hard missing — ask to auto-install
        echo -e "  ${YELLOW}${BOLD}Missing required dependencies.${NC}"
    else
        echo -e "  ${YELLOW}${BOLD}Some optional dependencies are missing.${NC}"
    fi

    read -rp "  Auto-install missing dependencies? [Y/n] " ans
    ans="${ans:-Y}"

    if [[ "$ans" =~ ^[Yy]$ ]]; then
        echo ""
        install_system_deps || true

        # Install PySide6 if still missing
        if ! python3 -c "import PySide6" &>/dev/null; then
            install_pyside6 || true
        fi

        echo ""
        # Re-check after install
        if ! python3 -c "import PySide6" &>/dev/null; then
            err "PySide6 still not available. Cannot continue."
            exit 1
        fi
        ok "All required dependencies satisfied"
    else
        if [ "$missing" -eq 1 ]; then
            err "Required dependencies missing. Aborting."
            exit 1
        else
            warn "Continuing without optional dependencies."
        fi
    fi
}

generate_icon() {
    local size=$1
    local output=$2
    mkdir -p "$(dirname "$output")"
    python3 -c "
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPixmap, QPainter, QColor, QBrush, QPen

app = QApplication(sys.argv)
size = ${size}
pixmap = QPixmap(size, size)
pixmap.fill(Qt.transparent)
p = QPainter(pixmap)
p.setRenderHint(QPainter.Antialiasing)
p.setBrush(QBrush(QColor('#1a1a2e')))
p.setPen(Qt.NoPen)
p.drawEllipse(2, 2, size - 4, size - 4)
cx = size / 2.0
cy = size * 0.65
pw = max(2, size // 14)
p.setPen(QPen(QColor('#00d4ff'), pw, Qt.SolidLine, Qt.RoundCap))
p.setBrush(Qt.NoBrush)
for r in [size * 0.15, size * 0.27, size * 0.39]:
    rect = QRectF(cx - r, cy - r, r * 2, r * 2)
    p.drawArc(rect, 45 * 16, 90 * 16)
dot_r = max(2, size // 14)
p.setPen(Qt.NoPen)
p.setBrush(QBrush(QColor('#00d4ff')))
p.drawEllipse(QPointF(cx, cy), dot_r, dot_r)
p.end()
pixmap.save('${output}')
" 2>/dev/null
}

do_install() {
    info "Checking dependencies..."
    check_deps
    echo ""

    if [ ! -f "$SOURCE_FILE" ]; then
        err "main.py not found in $SCRIPT_DIR"
        exit 1
    fi

    if [ ! -f "$SCRIPT_DIR/themes.py" ]; then
        err "themes.py not found in $SCRIPT_DIR"
        exit 1
    fi

    # ── Install dir ──
    info "Creating install directory: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
    ok "Directory created"

    # ── Copy app ──
    info "Copying application files..."
    cp "$SOURCE_FILE" "$INSTALL_DIR/main.py"
    cp "$SCRIPT_DIR/themes.py" "$INSTALL_DIR/themes.py"
    ok "main.py + themes.py installed"

    # ── Config ──
    if [ ! -f "$CONFIG_FILE" ]; then
        info "Creating default config..."
        cat > "$CONFIG_FILE" << 'CONFIGEOF'
{
    "start_minimized": false,
    "scan_interval": 3,
    "show_signal_bars": true,
    "auto_refresh": true,
    "animations": true,
    "close_to_tray": true,
    "show_tray_notifications": false,
    "theme": "Dark"
}
CONFIGEOF
        ok "config.json created"
    else
        ok "config.json preserved (existing)"
    fi

    # ── Icons ──
    info "Generating icons..."
    generate_icon 48 "$ICON_48"
    generate_icon 128 "$ICON_128"
    generate_icon 256 "$ICON_256"
    # Also put one in install dir for the app
    cp "$ICON_256" "$INSTALL_DIR/nzscan.png" 2>/dev/null || true
    ok "Icons generated (48, 128, 256)"

    # ── Desktop entry ──
    info "Creating desktop entry..."
    mkdir -p "$(dirname "$DESKTOP_FILE")"
    cat > "$DESKTOP_FILE" << DESKTOPEOF
[Desktop Entry]
Name=NZscan
Comment=WiFi Scanner
Exec=$BIN_FILE
Icon=nzscan
Terminal=false
Type=Application
Categories=Network;System;Monitor;
Keywords=wifi;scanner;network;signal;
StartupNotify=true
DESKTOPEOF
    ok "Desktop entry created"

    # ── Launcher ──
    info "Creating launcher..."
    mkdir -p "$(dirname "$BIN_FILE")"
    cat > "$BIN_FILE" << LAUNCHEREOF
#!/bin/bash
cd "$INSTALL_DIR"
exec python3 "$INSTALL_DIR/main.py" "\$@"
LAUNCHEREOF
    chmod +x "$BIN_FILE"
    ok "Launcher created: $BIN_FILE"

    # ── Update desktop database ──
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    fi
    if command -v gtk-update-icon-cache &>/dev/null; then
        gtk-update-icon-cache -f -t "$ICON_DIR" 2>/dev/null || true
    fi

    # ── Check PATH ──
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        warn "$HOME/.local/bin is not in PATH"
        warn "Add this to your shell config:  export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi

    echo ""
    echo -e "${GREEN}${BOLD}══════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  NZscan installed successfully!${NC}"
    echo -e "${GREEN}${BOLD}══════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${DIM}App:${NC}    $INSTALL_DIR/main.py"
    echo -e "  ${DIM}Config:${NC} $CONFIG_FILE"
    echo -e "  ${DIM}Run:${NC}    ${CYAN}nzscan${NC} or find it in your app menu"
    echo ""
}

do_update() {
    if [ ! -d "$INSTALL_DIR" ]; then
        err "NZscan is not installed. Run install first."
        exit 1
    fi

    if [ ! -f "$SOURCE_FILE" ]; then
        err "main.py not found in $SCRIPT_DIR"
        exit 1
    fi

    info "Checking dependencies..."
    check_deps
    echo ""

    info "Updating application..."
    cp "$SOURCE_FILE" "$INSTALL_DIR/main.py"
    cp "$SCRIPT_DIR/themes.py" "$INSTALL_DIR/themes.py"
    ok "main.py + themes.py updated"

    info "Regenerating icons..."
    generate_icon 48 "$ICON_48"
    generate_icon 128 "$ICON_128"
    generate_icon 256 "$ICON_256"
    cp "$ICON_256" "$INSTALL_DIR/nzscan.png" 2>/dev/null || true
    ok "Icons updated"

    ok "Config preserved: $CONFIG_FILE"

    echo ""
    echo -e "${GREEN}${BOLD}  NZscan updated successfully!${NC}"
    echo ""
}

do_uninstall() {
    echo ""
    echo -e "${YELLOW}${BOLD}  This will completely remove NZscan:${NC}"
    echo -e "  ${DIM}• Application files${NC}"
    echo -e "  ${DIM}• Configuration${NC}"
    echo -e "  ${DIM}• Desktop entry & icons${NC}"
    echo -e "  ${DIM}• Launcher script${NC}"
    echo ""
    read -rp "  Are you sure? [y/N] " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        info "Cancelled."
        exit 0
    fi

    echo ""

    if [ -d "$INSTALL_DIR" ]; then
        rm -rf "$INSTALL_DIR"
        ok "Removed $INSTALL_DIR"
    fi

    if [ -f "$DESKTOP_FILE" ]; then
        rm -f "$DESKTOP_FILE"
        ok "Removed desktop entry"
    fi

    for icon in "$ICON_48" "$ICON_128" "$ICON_256"; do
        if [ -f "$icon" ]; then
            rm -f "$icon"
        fi
    done
    ok "Removed icons"

    if [ -f "$BIN_FILE" ]; then
        rm -f "$BIN_FILE"
        ok "Removed launcher"
    fi

    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    fi
    if command -v gtk-update-icon-cache &>/dev/null; then
        gtk-update-icon-cache -f -t "$ICON_DIR" 2>/dev/null || true
    fi

    echo ""
    echo -e "${GREEN}${BOLD}  NZscan completely removed.${NC}"
    echo ""
}

show_status() {
    if [ -d "$INSTALL_DIR" ]; then
        echo -e "  Status:  ${GREEN}Installed${NC}"
        echo -e "  Path:    ${DIM}$INSTALL_DIR${NC}"
        if [ -f "$CONFIG_FILE" ]; then
            echo -e "  Config:  ${DIM}$CONFIG_FILE${NC}"
        fi
    else
        echo -e "  Status:  ${DIM}Not installed${NC}"
    fi
    echo ""
}

# ── Main ──
header

# If argument given, run directly
if [ $# -ge 1 ]; then
    case "$1" in
        install)   do_install ;;
        update)    do_update ;;
        uninstall) do_uninstall ;;
        *)
            err "Unknown option: $1"
            echo "Usage: $0 [install|update|uninstall]"
            exit 1
            ;;
    esac
    exit 0
fi

# Interactive menu
show_status

echo -e "  ${BOLD}What would you like to do?${NC}"
echo ""
echo -e "    ${CYAN}1${NC})  Install"
echo -e "    ${CYAN}2${NC})  Update"
echo -e "    ${CYAN}3${NC})  Uninstall"
echo -e "    ${CYAN}4${NC})  Exit"
echo ""
read -rp "  Choose [1-4]: " choice

case "$choice" in
    1) do_install ;;
    2) do_update ;;
    3) do_uninstall ;;
    4) echo ""; info "Bye!"; exit 0 ;;
    *) err "Invalid choice"; exit 1 ;;
esac
