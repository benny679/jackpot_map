import socket
import ipaddress
import json
import os
import csv
import requests
from datetime import datetime

def get_client_ip():
    """
    Attempt to get the client's IP address using various methods.
    In Streamlit, direct IP detection is limited, so we use a combination of approaches.
    """
    try:
        # Method 1: Use an external service (only works when internet is available)
        response = requests.get('https://api.ipify.org', timeout=2)
        if response.status_code == 200:
            return response.text

        # Method 2: Try to get local IP
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        return local_ip
    except:
        # Fallback if all methods fail
        return "Unknown"

def is_ip_allowed(ip_address):
    """
    Check if the IP address is allowed based on allow/deny lists.
    Returns True if allowed, False if blocked.
    """
    # Load IP configuration from file
    try:
        with open("ip_config.json", "r") as f:
            ip_config = json.load(f)
    except FileNotFoundError:
        # Create default IP configuration if it doesn't exist
        ip_config = {
            "mode": "allow_all",  # Options: allow_all, deny_all, use_lists
            "allow_list": [],
            "deny_list": []
        }
        with open("ip_config.json", "w") as f:
            json.dump(ip_config, f, indent=4)

    # Handle unknown IPs
    if ip_address == "Unknown":
        # By default allow unknown IPs, but you can change this
        return True

    mode = ip_config.get("mode", "allow_all")

    # Check mode
    if mode == "allow_all":
        return True
    elif mode == "deny_all":
        return False
    elif mode == "use_lists":
        # Check if IP is in deny list
        for denied_ip in ip_config.get("deny_list", []):
            # Check if it's a single IP or a network range
            if "/" in denied_ip:  # CIDR notation
                if ipaddress.ip_address(ip_address) in ipaddress.ip_network(denied_ip):
                    return False
            elif ip_address == denied_ip:
                return False

        # If allow list is empty, allow all IPs not in deny list
        if not ip_config.get("allow_list", []):
            return True

        # Check if IP is in allow list
        for allowed_ip in ip_config.get("allow_list", []):
            # Check if it's a single IP or a network range
            if "/" in allowed_ip:  # CIDR notation
                if ipaddress.ip_address(ip_address) in ipaddress.ip_network(allowed_ip):
                    return True
            elif ip_address == allowed_ip:
                return True

        # If we got here, IP is not in allow list
        return False

    # Default to allow if something went wrong
    return True

def log_ip_activity(username, activity_type, ip_address):
    """
    Log IP-based activity to a separate file for monitoring.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Create logs directory if it doesn't exist
    if not os.path.exists("logs"):
        os.makedirs("logs")

    log_file = "logs/ip_activity.csv"

    # Check if file exists, create with header if it doesn't
    file_exists = os.path.isfile(log_file)

    with open(log_file, "a", newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Username", "Activity", "IP Address"])
        writer.writerow([timestamp, username, activity_type, ip_address])
