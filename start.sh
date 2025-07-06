#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

# Update package lists and install required system libraries
apt-get update && apt-get install -y libopus0 libopus-dev

# Download static ffmpeg binary (Linux 64-bit)
curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o ffmpeg.tar.xz

# Extract the tarball
tar -xf ffmpeg.tar.xz

# Move ffmpeg binary to project root (adjust if multiple matches)
mv ffmpeg-*-amd64-static/ffmpeg ./ffmpeg

# Make ffmpeg executable
chmod +x ./ffmpeg

# Clean up extracted folder and tarball
rm -rf ffmpeg-*-amd64-static ffmpeg.tar.xz

# Run the bot
python bot1.py
