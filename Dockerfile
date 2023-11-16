#centOS
FROM nvidia/cuda:11.1.1-devel-ubi8

# Enable AppStream and install Python 3.9
RUN yum -y module enable python39
RUN yum install -y python39
RUN yum install -y python39-devel
RUN python3.9 --version || (echo "Python installation failed" && exit 1)
# Install pip (if not already included)
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.9

# Install NSS (Network Security Services) for Electron
RUN yum install -y nss
# Install ATK (Accessibility Toolkit)
RUN yum install -y atk
# Install at-spi2-atk for Electron
RUN yum install -y at-spi2-atk
# Install CUPS (Common UNIX Printing System) libraries for Electron
RUN yum install -y cups-libs
# Install GTK+ 3 for Electron
RUN yum install -y gtk3
# Install GBM (Generic Buffer Manager) library for Electron
RUN yum install -y mesa-libgbm
# Install ALSA (Advanced Linux Sound Architecture) libraries for Electron
RUN yum install -y alsa-lib

# Enable Node.js AppStream and install Node.js
RUN yum module enable -y nodejs:12
RUN yum install -y nodejs

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