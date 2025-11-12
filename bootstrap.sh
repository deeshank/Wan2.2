#!/bin/bash
set -e

echo "=========================================="
echo "Wan2.2 I2V FastAPI Server Bootstrap"
echo "=========================================="

WORKSPACE="/workspace"
REPO_URL="https://github.com/deeshank/Wan2.2"
BRANCH="dev"
MODEL_NAME="Wan2.2-I2V-A14B"

cd $WORKSPACE

# Install system dependencies
echo "Installing system dependencies..."
apt-get update && apt-get install -y \
    git \
    wget \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Clone repository
if [ -d "Wan2.2" ]; then
    echo "Repository already exists, pulling latest changes..."
    cd Wan2.2
    git fetch origin
    git checkout $BRANCH
    git pull origin $BRANCH
else
    echo "Cloning repository from $REPO_URL (branch: $BRANCH)..."
    git clone -b $BRANCH $REPO_URL
    cd Wan2.2
fi

echo "Installing Python dependencies..."
pip install --upgrade pip setuptools wheel ninja

echo "Installing flash-attn (this may take 5-10 minutes)..."
pip install flash-attn --no-build-isolation

echo "Installing core requirements..."
pip install -r requirements.txt

echo "Installing FastAPI dependencies..."
pip install fastapi uvicorn python-multipart aiofiles

# Optional: Install Speech-to-Video dependencies (uncomment if needed)
# echo "Installing Speech-to-Video dependencies..."
# pip install -r requirements_s2v.txt

# Optional: Install Wan-Animate dependencies (uncomment if needed)
# echo "Installing Wan-Animate dependencies..."
# pip install -r requirements_animate.txt

# Download model weights if not present
if [ -d "$MODEL_NAME" ]; then
    echo "Model weights already exist at $MODEL_NAME"
else
    echo "Downloading model weights (~100GB, this will take 15-30 minutes)..."
    pip install "huggingface_hub[cli]"
    huggingface-cli download Wan-AI/$MODEL_NAME --local-dir ./$MODEL_NAME
fi

echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "Starting FastAPI server on port 8000..."
echo "API will be available at: http://0.0.0.0:8000"
echo ""

# Start the server
python server.py
