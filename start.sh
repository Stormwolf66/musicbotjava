#!/bin/bash

# Update package lists and install libopus0 for Discord voice support
apt-get update && apt-get install -y libopus0

# Download static ffmpeg binary (Linux 64-bit)
curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o ffmpeg.tar.xz

# Extract the tarball
tar -xf ffmpeg.tar.xz

# Move and rename ffmpeg binary to project root
mv ffmpeg-*-amd64-static/ffmpeg ./ffmpeg

# Make ffmpeg executable
chmod +x ./ffmpeg

# Remove extracted folder and archive to keep clean (optional)
rm -rf ffmpeg-*-amd64-static ffmpeg.tar.xz

# Start your bot
python bot1.py
