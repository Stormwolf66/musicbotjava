#!/bin/bash
set -e  # Exit on any error

# Update package list and install dependencies
apt-get update && apt-get install -y ffmpeg libopus0 libopus-dev python3-pip

# Optionally upgrade pip and install python dependencies from requirements.txt if you have one
# pip3 install --upgrade pip
# pip3 install -r requirements.txt

# Run the bot
python3 bot.py
