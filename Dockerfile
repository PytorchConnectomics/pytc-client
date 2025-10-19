#centOS
FROM nvidia/cuda:11.1.1-devel-ubi8

# Enable AppStream and install Python 3.9 and git
RUN yum -y module enable python39 && \
    yum install -y python39-3.9.2 && \
    yum install -y python39-devel-3.9.2 && \
    yum install -y git && \
    yum clean all && \ 
    (python3.9 --version || echo "Python installation failed" && exit 1)

# Create a symbolic link to bind python to python3.9
RUN ln -s /usr/bin/python3.9 /usr/bin/python

# Install pip (if not already included)
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python

# Set working directory 
WORKDIR /app

# Install dependencies
RUN pip3 install --no-cache-dir torch==1.9.0 torchvision==0.10.0 cuda-python==11.1.1

# Download pytorch_connectomics at specific commit (version 1.0)
RUN git clone https://github.com/zudi-lin/pytorch_connectomics.git /app/pytorch_connectomics && \
    cd /app/pytorch_connectomics && \
    git checkout 20ccfde

COPY ./samples_pytc /app/samples_pytc
COPY ./server_pytc /app/server_pytc
COPY ./server_api /app/server_api

WORKDIR /app/pytorch_connectomics
RUN yum install -y libglvnd-glx-1.3.2 && \
    yum clean all && \
    pip3 install --no-cache-dir --editable .

WORKDIR /app/server_api
RUN pip3 install --no-cache-dir -r requirements.txt

WORKDIR /app
# Copies the startup scripts, and runs it at CMD
COPY ./start.sh /app/
COPY ./setup_pytorch_connectomics.sh /app/
RUN chmod +x start.sh setup_pytorch_connectomics.sh

# Expose ports
EXPOSE 4242 4243 4244 6006
CMD [ "./start.sh"]