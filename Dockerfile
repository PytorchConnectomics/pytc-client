#centOS
FROM nvidia/cuda:11.1.1-devel-ubi8

# Enable AppStream and install Python 3.9
RUN yum -y module enable python39
RUN yum install -y python39
RUN yum install -y python39-devel
RUN python3.9 --version || (echo "Python installation failed" && exit 1)
# Create a symbolic link to bind python to python3.9
RUN ln -s /usr/bin/python3.9 /usr/bin/python

# Install pip (if not already included)
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python

# Set working directory 
WORKDIR /app

# Install dependencies
RUN pip3 install torch torchvision cuda-python

COPY ./pytorch_connectomics /app/pytorch_connectomics
COPY ./samples_pytc /app/samples_pytc
COPY ./server_pytc /app/server_pytc
COPY ./server_api /app/server_api

WORKDIR /app/pytorch_connectomics
RUN yum install -y libglvnd-glx
RUN pip3 install --editable .

WORKDIR /app/server_api
RUN pip3 install -r requirements.txt

WORKDIR /app
# Copies the startup script, and runs it at CMD
COPY ./start.sh /app/
RUN chmod +x start.sh

# Expose ports
EXPOSE 4242 4243 4244 6006
CMD [ "./start.sh"]