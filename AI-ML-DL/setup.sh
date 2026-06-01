#!/bin/bash
# AI-ML-DL Learning Environment Setup Script

set -e

ENV_NAME="ai-ml-env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================"
echo "  AI/ML/DL Learning Environment Setup"
echo "============================================"
echo ""

# Create virtual environment
if [ -d "$SCRIPT_DIR/$ENV_NAME" ]; then
    echo "[!] Virtual environment '$ENV_NAME' already exists."
    read -p "    Recreate it? (y/N): " choice
    if [[ "$choice" =~ ^[Yy]$ ]]; then
        rm -rf "$SCRIPT_DIR/$ENV_NAME"
    else
        echo "    Using existing environment."
    fi
fi

if [ ! -d "$SCRIPT_DIR/$ENV_NAME" ]; then
    echo "[*] Creating virtual environment: $ENV_NAME"
    python3 -m venv "$SCRIPT_DIR/$ENV_NAME"
fi

# Activate
echo "[*] Activating virtual environment..."
source "$SCRIPT_DIR/$ENV_NAME/bin/activate"

# Upgrade pip
echo "[*] Upgrading pip..."
pip install --upgrade pip -q

# Install minimal requirements
echo "[*] Installing minimal requirements..."
pip install -r "$SCRIPT_DIR/requirements-minimal.txt" -q

# Verify installation
echo ""
echo "[*] Verifying installation..."
python3 -c "
import numpy; print(f'  numpy        {numpy.__version__}')
import pandas; print(f'  pandas       {pandas.__version__}')
import matplotlib; print(f'  matplotlib   {matplotlib.__version__}')
import seaborn; print(f'  seaborn      {seaborn.__version__}')
import sklearn; print(f'  scikit-learn  {sklearn.__version__}')
import scipy; print(f'  scipy        {scipy.__version__}')
print('\n  All packages installed successfully!')
"

# Welcome message
echo ""
echo "============================================"
echo "  Setup Complete!"
echo "============================================"
echo ""
echo "  To activate the environment:"
echo "    source $ENV_NAME/bin/activate"
echo ""
echo "  Learning Path:"
echo "    01-Mathematics-Foundations/"
echo "    02-Data-Preprocessing/"
echo "    03-Machine-Learning/"
echo "    04-Deep-Learning/"
echo "    05-MLOps/"
echo "    06-Real-World-Projects/"
echo ""
echo "  For deep learning projects, install full requirements:"
echo "    pip install -r requirements.txt"
echo ""
echo "  Happy Learning!"
echo "============================================"
