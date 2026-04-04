#!/bin/bash

# KPI Daemon Setup Script for Linux
# Usage: sudo ./setup_linux.sh --dashboard-url "http://192.168.1.100:5000" --node-id "linux_vm_1"

set -e

# Default values
DASHBOARD_URL="http://localhost:5000"
NODE_ID="linux_node_1"
POLLING_INTERVAL=5
INSTALL_DIR="/opt/daemon_node"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dashboard-url)
            DASHBOARD_URL="$2"
            shift 2
            ;;
        --node-id)
            NODE_ID="$2"
            shift 2
            ;;
        --polling-interval)
            POLLING_INTERVAL="$2"
            shift 2
            ;;
        --install-dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}KPI Daemon Setup Script for Linux${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root (use sudo)${NC}" 
   exit 1
fi

echo -e "${YELLOW}Configuration:${NC}"
echo "  Dashboard URL: $DASHBOARD_URL"
echo "  Node ID: $NODE_ID"
echo "  Polling Interval: ${POLLING_INTERVAL}s"
echo "  Install Directory: $INSTALL_DIR"
echo ""

# Step 1: Check Python installation
echo -e "${YELLOW}[1/6] Checking Python installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is not installed. Please install it first:${NC}"
    echo "  sudo apt-get update && sudo apt-get install python3 python3-pip"
    exit 1
fi
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP 'Python \K[0-9.]+')
echo -e "${GREEN}✓ Python ${PYTHON_VERSION} found${NC}"
echo ""

# Step 2: Create installation directory
echo -e "${YELLOW}[2/6] Creating installation directory...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Directory already exists at $INSTALL_DIR${NC}"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$INSTALL_DIR"
    else
        echo -e "${RED}Aborting setup${NC}"
        exit 1
    fi
fi
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/test_db"
mkdir -p "$INSTALL_DIR/logs"
echo -e "${GREEN}✓ Directory created${NC}"
echo ""

# Step 3: Copy project files
echo -e "${YELLOW}[3/6] Copying project files...${NC}"
cp "$PROJECT_DIR/daemon.py" "$INSTALL_DIR/"
cp "$PROJECT_DIR/db_connector.py" "$INSTALL_DIR/"
cp "$PROJECT_DIR/router.py" "$INSTALL_DIR/"
cp "$PROJECT_DIR/kpi_data.json" "$INSTALL_DIR/"
cp "$PROJECT_DIR/requirements.txt" "$INSTALL_DIR/"
echo -e "${GREEN}✓ Files copied${NC}"
echo ""

# Step 4: Install Python dependencies
echo -e "${YELLOW}[4/6] Installing Python dependencies...${NC}"
cd "$INSTALL_DIR"
python3 -m pip install --quiet -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Step 5: Configure daemon
echo -e "${YELLOW}[5/6] Configuring daemon...${NC}"
cat > "$INSTALL_DIR/config.json" << EOF
{
  "polling_interval_seconds": $POLLING_INTERVAL,
  "node_id": "$NODE_ID",
  "kpi_source": "kpi_data.json",
  "dashboard_url": "$DASHBOARD_URL",
  "database": {
    "type": "sqlite",
    "path": "$INSTALL_DIR/test_db/benchmark_test.db"
  }
}
EOF
echo -e "${GREEN}✓ Config created${NC}"
echo ""

# Step 6: Create systemd service
echo -e "${YELLOW}[6/6] Creating systemd service...${NC}"
cat > "/etc/systemd/system/kpi-daemon.service" << EOF
[Unit]
Description=KPI Monitoring Daemon - $NODE_ID
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/daemon.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=kpi-daemon

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable kpi-daemon.service
echo -e "${GREEN}✓ Service file created and enabled${NC}"
echo ""

# Summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. Start the daemon:"
echo "   ${GREEN}sudo systemctl start kpi-daemon.service${NC}"
echo ""
echo "2. Check daemon status:"
echo "   ${GREEN}sudo systemctl status kpi-daemon.service${NC}"
echo ""
echo "3. View live logs:"
echo "   ${GREEN}sudo journalctl -u kpi-daemon.service -f${NC}"
echo ""
echo "4. Verify connection to dashboard:"
echo "   ${GREEN}curl $DASHBOARD_URL/api/nodes${NC}"
echo ""
echo -e "${YELLOW}Configuration Details:${NC}"
echo "  Config file: $INSTALL_DIR/config.json"
echo "  Logs: journalctl -u kpi-daemon.service"
echo "  Database: $INSTALL_DIR/test_db/benchmark_test.db"
echo ""
