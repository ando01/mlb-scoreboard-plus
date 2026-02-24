#!/bin/bash
# MLB LED Scoreboard Installation Script

set -e

echo "========================================="
echo "  MLB LED Scoreboard Installation"
echo "========================================="
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ] || ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "Warning: This doesn't appear to be a Raspberry Pi"
    echo "Installing in development mode..."
    DEV_MODE=true
else
    echo "Detected Raspberry Pi"
    DEV_MODE=false
fi

# Check for Python 3.9+
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Found Python $PYTHON_VERSION"

if [ "$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 9) else 0)')" -eq 0 ]; then
    echo "Error: Python 3.9 or higher is required"
    exit 1
fi

# Install system dependencies
echo ""
echo "Installing system dependencies..."
if [ "$DEV_MODE" = false ]; then
    sudo apt-get update
    sudo apt-get install -y \
        python3-pip \
        python3-dev \
        python3-venv \
        libatlas-base-dev \
        git

    # Install RGB matrix library
    if [ ! -d "rpi-rgb-led-matrix" ]; then
        echo "Cloning rpi-rgb-led-matrix..."
        git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
        cd rpi-rgb-led-matrix
        make build-python PYTHON=$(which python3)
        sudo make install-python PYTHON=$(which python3)
        cd ..
    fi
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Copy example config if needed
if [ ! -f ".env" ]; then
    echo ""
    echo "Creating .env file..."
    cp .env.example .env
    echo "Please edit .env to configure your settings"
fi

# Make scripts executable
chmod +x main.py
chmod +x install.sh

# Install systemd service (optional)
if [ "$DEV_MODE" = false ]; then
    echo ""
    read -p "Install systemd service for auto-start? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        INSTALL_DIR=$(pwd)
        sudo bash -c "cat > /etc/systemd/system/mlb-scoreboard.service << EOF
[Unit]
Description=MLB LED Scoreboard
After=network.target

[Service]
Type=simple
# Root required for GPIO/LED matrix hardware access
User=root
WorkingDirectory=$INSTALL_DIR
Environment=\"PATH=$INSTALL_DIR/venv/bin\"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/main.py --web-ui
Restart=always
RestartSec=10
# Real-time CPU scheduling reduces OS jitter in software PWM
CPUSchedulingPolicy=rr
CPUSchedulingPriority=50
# Prevent OOM killer from targeting this process
OOMScoreAdjust=-500

[Install]
WantedBy=multi-user.target
EOF"

        sudo systemctl daemon-reload
        sudo systemctl enable mlb-scoreboard.service
        echo "Service installed! Use 'sudo systemctl start mlb-scoreboard' to start"
    fi
fi

echo ""
echo "========================================="
echo "  Installation Complete!"
echo "========================================="
echo ""
echo "To run the scoreboard:"
echo "  1. Edit .env to configure your settings"
echo "  2. Activate virtual environment: source venv/bin/activate"
echo "  3. Run: python3 main.py"
echo ""
echo "To run with web UI:"
echo "  python3 main.py --web-ui"
echo ""
echo "To run only web UI (for configuration):"
echo "  python3 main.py --web-ui-only"
echo ""
echo "Web UI will be available at http://[your-pi-ip]:8080"
echo ""
