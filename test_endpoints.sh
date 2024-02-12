#!/bin/bash
# Get the IP address of the default network interface
SERVER_IP=$(hostname -I | awk '{print $1}')

# Check if SERVER_IP is empty
if [ -z "$SERVER_IP" ]; then
    echo "Failed to retrieve server IP address."
    exit 1
fi

# Endpoint URLS
ENDPOINT_1="http://$SERVER_IP:4243/hello"
ENDPOINT_2="http://$SERVER_IP:4243/neuroglancer"
ENDPOINT_3="http://$SERVER_IP:4243/start_model_training"
ENDPOINT_4="http://$SERVER_IP:4243/stop_model_training"
ENDPOINT_5="http://$SERVER_IP:4243/start_model_inference"
ENDPOINT_6="http://$SERVER_IP:4243/stop_model_inference"
ENDPOINT_7="http://$SERVER_IP:4243/get_tensorboard_url"

# Test endpoint 1
curl -s -o /dev/null -w "%{http_code} " $ENDPOINT_1
STATUS_1=$?

# Test endpoint 2
curl -s -o /dev/null -w "%{http_code} " $ENDPOINT_2
STATUS_2=$?

# Test endpoint 3
curl -s -o /dev/null -w "%{http_code} " $ENDPOINT_3
STATUS_3=$?

# Test endpoint 4
curl -s -o /dev/null -w "%{http_code} " $ENDPOINT_4
STATUS_4=$?

# Test endpoint 5
curl -s -o /dev/null -w "%{http_code} " $ENDPOINT_5
STATUS_5=$?

# Test endpoint 6
curl -s -o /dev/null -w "%{http_code} " $ENDPOINT_6
STATUS_6=$?

# Test endpoint 7
curl -s -o /dev/null -w "%{http_code} " $ENDPOINT_7
STATUS_7=$?


# Check the status and exit accordingly
if [ $STATUS_1 -eq 200 ] && [ $STATUS_2 -eq 200 ] && [ $STATUS_3 -eq 200 ] && [ $STATUS_4 -eq 200 ] && [ $STATUS_5 -eq 200 ] && [ $STATUS_6 -eq 200 ] && [ $STATUS_7 -eq 200 ]; then
    echo "All endpoints are reachable."
    exit 0
else
    echo "One or more endpoints are not reachable."
    exit 1
fi
