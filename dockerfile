FROM python:3.12-slim

# Install ffmpeg and other dependencies
RUN apt-get update && apt-get install -y ffmpeg

# Set work directory
WORKDIR /app

# Copy your files
COPY . .

# Install python dependencies
RUN pip install -r requirements.txt

CMD ["python", "bot.py"]
