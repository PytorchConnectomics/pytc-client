# Start with the base Ubuntu image
FROM ubuntu:latest

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Update and install software properties
RUN apt-get update && apt-get install -y software-properties-common

# Add deadsnakes PPA for Python installations
RUN add-apt-repository ppa:deadsnakes/ppa

# Install Python
RUN apt-get update && apt-get install -y python3.9 python3.9-dev python3.9-distutils python3.9-venv

# Install pip
RUN apt-get install -y curl && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.9

# Install Node.js, npm, and necessary libraries for Electron
RUN apt-get update && \
    apt-get install -y nodejs npm \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxtst6 \
    libcups2 \
    libxss1 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libgtk-3-0 \
    libgbm1 \
    libgbm-dev
    
# Set working directory 
WORKDIR /app

# Copy source code
COPY . .

# Install dependencies
RUN pip3 install torch torchvision cuda-python

WORKDIR /app/client 
RUN npm cache clean --force
RUN npm install --include=dev

RUN npm run build

# Check for electron installation
RUN if ! npx electron --version --no-sandbox; then echo "Electron not found!" && exit 1; fi

WORKDIR /app/server_api
RUN pip3 install -r requirements.txt

WORKDIR /app
# Copies the startup script, and runs it at CMD
COPY start.sh .
RUN chmod +x start.sh

# Expose ports
EXPOSE 4242 4243