import streamlit as st
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta
import csv
from .ip_manager import get_client_ip, is_ip_allowed, log_ip_activity

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

# Function to load user credentials from file
def load_credentials():
    """Load user credentials from a JSON file."""
    # Get the absolute path to the utils directory
    utils_dir = os.path.dirname(os.path.abspath(__file__))
    credentials_path = os.path.join(utils_dir, "credentials.json")
    
    try:
        with open(credentials_path, "r") as f:
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

        # Create directory if it doesn't exist (shouldn't be needed since we're in utils)
        os.makedirs(utils_dir, exist_ok=True)

        with open(credentials_path, "w") as f:
            json.dump(default_credentials, f)
        return default_credentials

# Load user credentials
USER_CREDENTIALS = load_credentials()

def initialize_session_state():
    """Initialize session state variables if they don't exist."""
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
        # Get the absolute path to the utils directory
        utils_dir = os.path.dirname(os.path.abspath(__file__))
        logs_dir = os.path.join(utils_dir, "logs")
        rate_limit_file = os.path.join(logs_dir, "rate_limits.json")
        
        # Create rate limiting file if it doesn't exist
        if not os.path.exists(rate_limit_file):
            os.makedirs(logs_dir, exist_ok=True)
            with open(rate_limit_file, "w") as f:
                json.dump({}, f)

        # Load rate limiting data
        with open(rate_limit_file, "r") as f:
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
        # Get the absolute path to the utils directory
        utils_dir = os.path.dirname(os.path.abspath(__file__))
        logs_dir = os.path.join(utils_dir, "logs")
        rate_limit_file = os.path.join(logs_dir, "rate_limits.json")
        
        # Create rate limiting file if it doesn't exist
        if not os.path.exists(rate_limit_file):
            os.makedirs(logs_dir, exist_ok=True)
            with open(rate_limit_file, "w") as f:
                json.dump({}, f)

        # Load rate limiting data
        with open(rate_limit_file, "r") as f:
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
        with open(rate_limit_file, "w") as f:
            json.dump(rate_limits, f)

    def log_login_activity(username, status, ip_address):
        """Log login activity to a file with IP information"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get the absolute path to the utils directory
        utils_dir = os.path.dirname(os.path.abspath(__file__))
        logs_dir = os.path.join(utils_dir, "logs")
        log_file = os.path.join(logs_dir, "login_activity.csv")
        
        # Create logs directory if it doesn't exist
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)

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

    # Instead of calling st.rerun() directly, set a flag in session state
    st.session_state["authenticated"] = False
    st.session_state["username"] = None
    st.session_state["user_role"] = None
    st.session_state["ip_address"] = None
    st.session_state["logout_requested"] = True  # Add this flag

# In your main app code, check for the logout flag
def check_logout_flag():
    """Check if logout was requested and perform rerun if needed"""
    if st.session_state.get("logout_requested", False):
        st.session_state["logout_requested"] = False  # Reset the flag
        st.rerun()  # This will work because it's not in a callback context

# Add this check early in your app's flow, not in a callback
# For example, in your main app file after initializing session state:
# initialize_session_state()
# check_logout_flag()  # Add this line to check for logout requests
