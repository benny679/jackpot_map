import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os
import streamlit as st
import hashlib
import hmac
import json
import requests
from datetime import datetime, timedelta
import socket
import ipaddress
import csv
import time

# Set page configuration
st.set_page_config(
    page_title="Jackpot Map Dashboard",
    page_icon="🎮",
    layout="wide"
)

# ---------- IP DETECTION FUNCTIONS ----------

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

# ---------- AUTHENTICATION FUNCTIONS ----------

def check_password():
    """Returns `True` if the user had the correct password."""

    def login_form():
        """Form for entering password"""
        with st.form("Credentials"):
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.form_submit_button("Log In", on_click=password_entered)

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        username = st.session_state["username"]
        password = st.session_state["password"]

        # Get client IP
        ip_address = get_client_ip()

        # Check if IP is allowed
        if not is_ip_allowed(ip_address):
            st.session_state["authentication_error"] = "Access from your IP address is not allowed."
            log_ip_activity(username, "blocked_ip", ip_address)
            return False

        # Check for rate limiting (prevent brute force attacks)
        if not check_rate_limit(username, ip_address):
            st.session_state["authentication_error"] = "Too many login attempts. Please try again later."
            log_ip_activity(username, "rate_limited", ip_address)
            return False

        # Get hashed password from credentials file
        if username in USER_CREDENTIALS:
            stored_password = USER_CREDENTIALS[username]["password"]
            stored_salt = USER_CREDENTIALS[username]["salt"]

            # Hash the entered password with the stored salt
            hashed_password = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                stored_salt.encode('utf-8'),
                100000
            ).hex()

            if hmac.compare_digest(hashed_password, stored_password):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.session_state["user_role"] = USER_CREDENTIALS[username]["role"]
                st.session_state["login_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state["ip_address"] = ip_address

                log_login_activity(username, "success", ip_address)
                log_ip_activity(username, "successful_login", ip_address)
                return True

        # If we get here, authentication failed
        st.session_state["authenticated"] = False
        log_login_activity(username, "failed", ip_address)
        log_ip_activity(username, "failed_login", ip_address)

        # Only increment failed attempts if not rate limited
        increment_failed_attempts(username, ip_address)

        st.session_state["authentication_error"] = "Username or password incorrect"
        return False

    def check_rate_limit(username, ip_address):
        """
        Check if the user or IP is being rate limited due to too many failed attempts.
        Returns True if the user is allowed to attempt login, False if rate limited.
        """
        # Create rate limiting file if it doesn't exist
        if not os.path.exists("logs/rate_limits.json"):
            os.makedirs("logs", exist_ok=True)
            with open("logs/rate_limits.json", "w") as f:
                json.dump({}, f)

        # Load rate limiting data
        with open("logs/rate_limits.json", "r") as f:
            rate_limits = json.load(f)

        current_time = time.time()

        # Check username rate limiting
        if username in rate_limits:
            user_data = rate_limits[username]
            if current_time < user_data.get("reset_time", 0):
                return False

        # Check IP rate limiting
        ip_key = f"ip_{ip_address}"
        if ip_key in rate_limits:
            ip_data = rate_limits[ip_key]
            if current_time < ip_data.get("reset_time", 0):
                return False

        return True

    def increment_failed_attempts(username, ip_address):
        """
        Increment failed login attempts for a username and IP address.
        Implements rate limiting after too many failed attempts.
        """
        # Create rate limiting file if it doesn't exist
        if not os.path.exists("logs/rate_limits.json"):
            os.makedirs("logs", exist_ok=True)
            with open("logs/rate_limits.json", "w") as f:
                json.dump({}, f)

        # Load rate limiting data
        with open("logs/rate_limits.json", "r") as f:
            rate_limits = json.load(f)

        current_time = time.time()

        # Update username attempts
        if username in rate_limits:
            user_data = rate_limits[username]
            # Reset if the window has passed
            if current_time > user_data.get("window_end", 0):
                user_data = {"attempts": 1, "window_end": current_time + 300}  # 5-minute window
            else:
                user_data["attempts"] = user_data.get("attempts", 0) + 1

                # Rate limit after 5 failed attempts
                if user_data["attempts"] >= 5:
                    user_data["reset_time"] = current_time + 1800  # 30-minute lockout
                    log_ip_activity(username, "rate_limited_user", ip_address)

            rate_limits[username] = user_data
        else:
            rate_limits[username] = {"attempts": 1, "window_end": current_time + 300}

        # Update IP attempts
        ip_key = f"ip_{ip_address}"
        if ip_key in rate_limits:
            ip_data = rate_limits[ip_key]
            # Reset if the window has passed
            if current_time > ip_data.get("window_end", 0):
                ip_data = {"attempts": 1, "window_end": current_time + 300}  # 5-minute window
            else:
                ip_data["attempts"] = ip_data.get("attempts", 0) + 1

                # Rate limit after 10 failed attempts from same IP
                if ip_data["attempts"] >= 10:
                    ip_data["reset_time"] = current_time + 3600  # 1-hour lockout
                    log_ip_activity(username, "rate_limited_ip", ip_address)

            rate_limits[ip_key] = ip_data
        else:
            rate_limits[ip_key] = {"attempts": 1, "window_end": current_time + 300}

        # Save updated rate limiting data
        with open("logs/rate_limits.json", "w") as f:
            json.dump(rate_limits, f)

    def log_login_activity(username, status, ip_address):
        """Log login activity to a file with IP information"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Create logs directory if it doesn't exist
        if not os.path.exists("logs"):
            os.makedirs("logs")

        log_file = "logs/login_activity.csv"

        # Check if file exists, create with header if it doesn't
        file_exists = os.path.isfile(log_file)

        with open(log_file, "a", newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Username", "Status", "IP Address"])
            writer.writerow([timestamp, username, status, ip_address])

    # Return True if the user is authenticated
    if st.session_state.get("authenticated"):
        # Check for session timeout (optional)
        login_time = datetime.strptime(st.session_state.get("login_time"), "%Y-%m-%d %H:%M:%S")
        if datetime.now() - login_time > timedelta(hours=8):  # 8-hour timeout
            st.session_state["authenticated"] = False
            st.warning("Your session has expired. Please log in again.")
            login_form()
            return False
        return True

    # Show login form if not authenticated
    if "authentication_error" in st.session_state:
        st.error(st.session_state["authentication_error"])
        # Remove the error message after it's been displayed
        del st.session_state["authentication_error"]

    login_form()
    return False

def logout():
    """Log out the user and log the activity"""
    if "username" in st.session_state and "ip_address" in st.session_state:
        log_ip_activity(st.session_state["username"], "logout", st.session_state["ip_address"])

    st.session_state["authenticated"] = False
    st.session_state["username"] = None
    st.session_state["user_role"] = None
    st.session_state["ip_address"] = None
    st.experimental_rerun()

# Function to load user credentials from file
# In a production app, you would use a secure database instead
def load_credentials():
    """Load user credentials from a JSON file."""
    try:
        with open("credentials.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        # Create a default admin user if file doesn't exist
        default_salt = secrets.token_hex(16)
        default_credentials = {
            "admin": {
                "password": hashlib.pbkdf2_hmac('sha256', "admin".encode('utf-8'),
                                               default_salt.encode('utf-8'), 100000).hex(),
                "salt": default_salt,
                "role": "admin"
            }
        }

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname("credentials.json"), exist_ok=True)

        with open("credentials.json", "w") as f:
            json.dump(default_credentials, f)
        return default_credentials

# Try to import secrets module - only needed for salt generation
try:
    import secrets
except ImportError:
    # Fallback for older Python versions
    import random
    import string
    def token_hex(nbytes):
        return ''.join(random.choice(string.hexdigits) for _ in range(nbytes * 2))
    # Assign our function to the missing module
    class SecretsModule:
        @staticmethod
        def token_hex(nbytes):
            return token_hex(nbytes)
    secrets = SecretsModule()

# Load user credentials
USER_CREDENTIALS = load_credentials()

# Initialize session state variables if they don't exist
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "username" not in st.session_state:
    st.session_state["username"] = None
if "user_role" not in st.session_state:
    st.session_state["user_role"] = None
if "login_time" not in st.session_state:
    st.session_state["login_time"] = None
if "ip_address" not in st.session_state:
    st.session_state["ip_address"] = None

# ---------- SLACK AND DATA FUNCTIONS ----------

# Use secrets or environment variables for sensitive information
SLACK_TOKEN = os.environ.get('SLACK_TOKEN')
CHANNEL_ID = os.environ.get('SLACK_CHANNEL_ID')

def upload_to_slack(file_path, message):
    """Upload a file to Slack and post a message about the upload using v2 API."""
    if not SLACK_TOKEN:
        st.warning("No Slack token provided. Set the SLACK_TOKEN environment variable.")
        return False

    client = WebClient(token=SLACK_TOKEN)
    try:
        response = client.files_upload_v2(channels=CHANNEL_ID, file=file_path)
        if response["ok"]:
            client.chat_postMessage(channel=CHANNEL_ID, text=message)
            st.success(f"File '{file_path}' uploaded and message posted successfully to Slack.")
            return True
        else:
            st.error(f"Failed to upload file: {response['error']}")
            return False
    except SlackApiError as e:
        st.error(f"Slack API Error: {str(e)}")
        return False

@st.cache_data(ttl=3600)  # Cache data for 1 hour
def load_sheet_data():
    """Load data from Google Sheets."""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Low Vol JPS").worksheet("Jackpot Map")
        data = sheet.get_all_values()
        headers = data.pop(0)
        df = pd.DataFrame(data, columns=headers)

        # Convert appropriate columns to numeric
        numeric_cols = df.columns[df.columns.str.contains('Amount|Level|Value|%|ID', case=False)]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='ignore')

        return df
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()

# ---------- MAIN APP ----------

# Check if the user is authenticated
if check_password():
    # Log the page view with IP
    if "username" in st.session_state and "ip_address" in st.session_state:
        log_ip_activity(st.session_state["username"], "page_view", st.session_state["ip_address"])

    # Display logout button in the sidebar
    st.sidebar.button("Logout", on_click=logout)

    # Display user information
    st.sidebar.info(f"Logged in as: {st.session_state['username']} ({st.session_state['user_role']})")

    # Display IP address (only for admins)
    if st.session_state["user_role"] == "admin":
        st.sidebar.info(f"Your IP: {st.session_state['ip_address']}")

    # Main app layout
    st.title("🎮 Jackpot Map Dashboard")

    # Sidebar for filters
    st.sidebar.title("Filters")
    st.sidebar.markdown("Refine your view using these filters:")

    # Load data from Google Sheets
    with st.spinner("Loading data from Google Sheets..."):
        df = load_sheet_data()

    if df.empty:
        st.warning("No data available. Please check your connection to Google Sheets.")
        st.stop()

    # Search filter at the top
    st.sidebar.subheader("Quick Search")
    search = st.sidebar.text_input("Search across all columns", "")

    # Advanced filtering
    st.sidebar.subheader("Advanced Filters")

    # Function to create filters with "All" option
    def create_filter(df, column):
        options = ["All"] + sorted(df[column].unique().tolist())
        return st.sidebar.selectbox(f"Filter by {column}", options)

    # Create filters for each column
    filters = {}
    filter_columns = ["Parent", "Operator", "Region", "License", "Accounts" ,"Game Name", "Provider", "Jackpot Group", "Type", "Dash ID"]

    for column in filter_columns:
        if column in df.columns:
            filters[column] = create_filter(df, column)

    # Apply filters
    filtered_df = df.copy()

    # Apply search filter if provided
    if search:
        filtered_df = filtered_df[filtered_df.astype(str).apply(
            lambda x: x.str.contains(search, case=False, na=False)).any(axis=1)]

    # Apply column filters (only when not "All")
    for column, value in filters.items():
        if value != "All":
            filtered_df = filtered_df[filtered_df[column] == value]

    # Display metrics
    st.subheader("Summary Metrics")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Records", f"{len(filtered_df)}")

    with col2:
        num_operators = filtered_df["Operator"].nunique() if "Operator" in filtered_df.columns else 0
        st.metric("Unique Operators", f"{num_operators}")

    with col3:
        num_games = filtered_df["Game Name"].nunique() if "Game Name" in filtered_df.columns else 0
        st.metric("Unique Games", f"{num_games}")

    # Display filtered data
    st.subheader("Filtered Data")
    st.dataframe(filtered_df, use_container_width=True)

    # Visualization section (only shown to certain roles)
    if st.session_state["user_role"] in ["admin", "analyst"]:
        st.subheader("Visualizations")

        tab1, tab2 = st.tabs(["Distribution Analysis", "Detailed Counts"])

        with tab1:
            # Distribution by region and operator
            if "Region" in filtered_df.columns and "Operator" in filtered_df.columns:
                region_operator_counts = filtered_df.groupby(["Region", "Operator"]).size().reset_index(name="Count")
                st.bar_chart(region_operator_counts.pivot(index="Region", columns="Operator", values="Count"))

        with tab2:
            # Detailed counts by different dimensions
            if "Provider" in filtered_df.columns:
                col1, col2 = st.columns(2)

                with col1:
                    provider_counts = filtered_df["Provider"].value_counts().reset_index()
                    provider_counts.columns = ["Provider", "Count"]
                    st.bar_chart(provider_counts.set_index("Provider"))

                with col2:
                    if "Jackpot Group" in filtered_df.columns:
                        jackpot_counts = filtered_df["Jackpot Group"].value_counts().reset_index()
                        jackpot_counts.columns = ["Jackpot Group", "Count"]
                        st.bar_chart(jackpot_counts.set_index("Jackpot Group"))

    # Export options (restricted by role)
    st.subheader("Export Data")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Download Filtered Data as CSV"):
            file_path = "jackpot_map_filtered.csv"
            filtered_df.to_csv(file_path, index=False)
            st.download_button(
                label="Download CSV",
                data=filtered_df.to_csv(index=False).encode('utf-8'),
                file_name="jackpot_map_filtered.csv",
                mime="text/csv"
            )

    # Slack upload only for admin users
    if st.session_state["user_role"] == "admin":
        with col2:
            slack_message = st.text_input("Slack Message (optional)", "Here's the latest jackpot map data:")
            if st.button("Upload Filtered Data to Slack"):
                if SLACK_TOKEN:
                    file_path = "jackpot_map_filtered.csv"
                    filtered_df.to_csv(file_path, index=False)
                    upload_to_slack(file_path, slack_message)
                else:
                    st.warning("Slack token not set. Please set the SLACK_TOKEN environment variable.")

    # Admin panel (only shown to admin users)
    if st.session_state["user_role"] == "admin":
        st.subheader("Admin Panel")

        # Create tabs for different admin functions
        admin_tab1, admin_tab2, admin_tab3 = st.tabs(["User Activity", "IP Management", "System Logs"])

        with admin_tab1:
            # Show recent login activity
            if os.path.exists("logs/login_activity.csv"):
                login_activity = pd.read_csv("logs/login_activity.csv")

                st.write("Recent Login Activity")

                # Filter options
                col1, col2 = st.columns(2)
                with col1:
                    filter_status = st.selectbox("Filter by Status", ["All", "success", "failed"])
                with col2:
                    filter_user = st.selectbox("Filter by User", ["All"] + list(set(login_activity["Username"].tolist())))

                # Apply filters
                filtered_activity = login_activity.copy()
                if filter_status != "All":
                    filtered_activity = filtered_activity[filtered_activity["Status"] == filter_status]
                if filter_user != "All":
                    filtered_activity = filtered_activity[filtered_activity["Username"] == filter_user]

                # Sort by most recent first
                filtered_activity = filtered_activity.sort_values("Timestamp", ascending=False)

                st.dataframe(filtered_activity, use_container_width=True)

        with admin_tab2:
            st.write("IP Address Management")

            # Load IP configuration
            try:
                with open("ip_config.json", "r") as f:
                    ip_config = json.load(f)
            except FileNotFoundError:
                ip_config = {
                    "mode": "allow_all",
                    "allow_list": [],
                    "deny_list": []
                }

            # IP configuration options
            st.subheader("IP Access Control")

            # Select mode
            mode = st.radio("IP Access Mode",
                            ["Allow All (default)", "Deny All", "Use Allow/Deny Lists"],
                            index=["allow_all", "deny_all", "use_lists"].index(ip_config.get("mode", "allow_all")))

            # Convert mode to internal representation
            if mode == "Allow All (default)":
                ip_config["mode"] = "allow_all"
            elif mode == "Deny All":
                ip_config["mode"] = "deny_all"
            else:
                ip_config["mode"] = "use_lists"

            # Allow/Deny list management
            if ip_config["mode"] == "use_lists":
                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("Allow List")
                    allow_list = st.text_area("IPs to Allow (one per line)",
                                             "\n".join(ip_config.get("allow_list", [])))
                    ip_config["allow_list"] = [ip.strip() for ip in allow_list.split("\n") if ip.strip()]

                with col2:
                    st.subheader("Deny List")
                    deny_list = st.text_area("IPs to Deny (one per line)",
                                            "\n".join(ip_config.get("deny_list", [])))
                    ip_config["deny_list"] = [ip.strip() for ip in deny_list.split("\n") if ip.strip()]

                st.info("You can use individual IPs (e.g., 192.168.1.1) or CIDR notation (e.g., 192.168.1.0/24)")

            # Save IP configuration
            if st.button("Save IP Configuration"):
                with open("ip_config.json", "w") as f:
                    json.dump(ip_config, f, indent=4)
                st.success("IP configuration saved successfully!")

            # Show IP activity logs
            st.subheader("IP Activity Logs")

            if os.path.exists("logs/ip_activity.csv"):
                ip_activity = pd.read_csv("logs/ip_activity.csv")

                # Filter options
                col1, col2 = st.columns(2)
                with col1:
                    filter_activity = st.selectbox("Filter by Activity",
                                                 ["All"] + list(set(ip_activity["Activity"].tolist())))
                with col2:
                    filter_ip = st.selectbox("Filter by IP",
                                           ["All"] + list(set(ip_activity["IP Address"].tolist())))

                # Apply filters
                filtered_ip_activity = ip_activity.copy()
                if filter_activity != "All":
                    filtered_ip_activity = filtered_ip_activity[filtered_ip_activity["Activity"] == filter_activity]
                if filter_ip != "All":
                    filtered_ip_activity = filtered_ip_activity[filtered_ip_activity["IP Address"] == filter_ip]

                # Sort by most recent first
                filtered_ip_activity = filtered_ip_activity.sort_values("Timestamp", ascending=False)

                st.dataframe(filtered_ip_activity, use_container_width=True)

        with admin_tab3:
            st.write("System Logs")

            # Show rate limiting information
            st.subheader("Rate Limiting Status")

            if os.path.exists("logs/rate_limits.json"):
                with open("logs/rate_limits.json", "r") as f:
                    rate_limits = json.load(f)

                # Create a dataframe for display
                rate_limit_data = []
                current_time = time.time()

                for key, data in rate_limits.items():
                    entry = {
                        "Type": "User" if not key.startswith("ip_") else "IP",
                        "Username/IP": key[3:] if key.startswith("ip_") else key,
                        "Attempts": data.get("attempts", 0),
                        "Status": "Locked" if current_time < data.get("reset_time", 0) else "Active",
                        "Lockout Expires": datetime.fromtimestamp(data.get("reset_time", 0)).strftime("%Y-%m-%d %H:%M:%S")
                                        if "reset_time" in data else "N/A"
                    }
                    rate_limit_data.append(entry)

                rate_limit_df = pd.DataFrame(rate_limit_data)
                st.dataframe(rate_limit_df, use_container_width=True)

                # Button to clear rate limits
                if st.button("Clear All Rate Limits"):
                    with open("logs/rate_limits.json", "w") as f:
                        json.dump({}, f)
                    st.success("Rate limits cleared successfully!")
                    st.experimental_rerun()

    # Footer with information
    st.markdown("---")
    st.markdown("Dashboard updates hourly from Google Sheets. Last update: " + pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"))
