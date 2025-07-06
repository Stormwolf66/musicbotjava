#!/bin/bash

# Download static ffmpeg binary
curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o ffmpeg.tar.xz

# Extract
tar -xf ffmpeg.tar.xz
mv ffmpeg-* ffmpeg-dir
mv ffmpeg-dir/ffmpeg ./ffmpeg
chmod +x ffmpeg

# Start your bot
python bot1.py
