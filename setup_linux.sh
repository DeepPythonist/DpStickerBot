#!/bin/bash

# DpStickerBot Linux Server Setup Script
# This script installs system dependencies required for the bot

echo "🚀 Setting up DpStickerBot on Linux Server..."

# Update system packages
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python 3 and pip
echo "🐍 Installing Python 3 and pip..."
sudo apt install -y python3 python3-pip python3-venv

# Install FFmpeg (required for video processing)
echo "🎬 Installing FFmpeg..."
sudo apt install -y ffmpeg

# Verify FFmpeg and ffprobe installation
echo "✅ Verifying FFmpeg installation..."
ffmpeg_version=$(ffmpeg -version 2>/dev/null | head -n 1)
ffprobe_version=$(ffprobe -version 2>/dev/null | head -n 1)

if [ $? -eq 0 ] && [ -n "$ffmpeg_version" ] && [ -n "$ffprobe_version" ]; then
    echo "✅ FFmpeg installed successfully: $ffmpeg_version"
    echo "✅ ffprobe installed successfully: $ffprobe_version"
else
    echo "❌ FFmpeg or ffprobe installation failed!"
    echo "💡 FFmpeg package should include both ffmpeg and ffprobe"
    exit 1
fi

# Create virtual environment
echo "📝 Creating Python virtual environment..."
python3 -m venv venv

# Activate virtual environment and install Python dependencies
echo "📚 Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ System setup completed successfully!"
echo ""
echo "🔧 Next steps:"
echo "1. Configure your bot token and settings in config.py"
echo "2. Setup MongoDB connection"
echo "3. Run the bot with: source venv/bin/activate && python bot.py" 