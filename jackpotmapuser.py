import streamlit as st
import time
import datetime
import json
import hashlib
import os
import pickle
from pathlib import Path

# Import your user management functions (assuming they're in a file called user_management.py)
# If your script is named differently, change the import accordingly
# from user_management import load_credentials, hash_password

# Function to hash password (copied from your script for direct usage)
def hash_password(password, salt):
    """Hash a password with a salt using PBKDF2"""
    return hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000  # 100,000 iterations
    ).hex()

# Function to load credentials (copied from your script for direct usage)
def load_credentials():
    """Load user credentials from a JSON file."""
    try:
        with open("credentials.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: credentials.json file not found. Please run the user management script first.")
        return {}

# Session timeout configuration (in seconds)
SESSION_TIMEOUT = 1800  # 30 minutes

# Function to create session folder and file
def setup_session_storage():
    session_dir = Path("./.streamlit/sessions")
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir

# Function to save session data to file
def save_session(session_id, data):
    session_dir = setup_session_storage()
    session_file = session_dir / f"{session_id}.pkl"
    with open(session_file, 'wb') as f:
        pickle.dump(data, f)

# Function to load session data from file
def load_session(session_id):
    session_dir = setup_session_storage()
    session_file = session_dir / f"{session_id}.pkl"
    if session_file.exists():
        try:
            with open(session_file, 'rb') as f:
                return pickle.load(f)
        except:
            return None
    return None

# Generate a unique session ID based on client info (will persist across refreshes)
def get_session_id():
    import socket
    client_ip = socket.gethostbyname(socket.gethostname())
    client_id = hashlib.md5(client_ip.encode()).hexdigest()
    return client_id

# Get the session ID for this client
session_id = get_session_id()

# Try to load existing session data
session_data = load_session(session_id)

# Initialize session state variables
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False if session_data is None else session_data.get('logged_in', False)
    
if 'login_time' not in st.session_state:
    st.session_state.login_time = None if session_data is None else session_data.get('login_time', None)
    
if 'username' not in st.session_state:
    st.session_state.username = None if session_data is None else session_data.get('username', None)
    
if 'role' not in st.session_state:
    st.session_state.role = None if session_data is None else session_data.get('role', None)
    
if 'last_activity' not in st.session_state:
    st.session_state.last_activity = None if session_data is None else session_data.get('last_activity', None)

def check_session_timeout():
    """Check if the session has timed out"""
    if st.session_state.logged_in and st.session_state.last_activity:
        current_time = time.time()
        time_elapsed = current_time - st.session_state.last_activity
        
        if time_elapsed > SESSION_TIMEOUT:
            # Session expired
            logout_user("Your session has expired due to inactivity.")
            return True
    return False

def update_activity():
    """Update the last activity timestamp and save session"""
    st.session_state.last_activity = time.time()
    
    # Save session data to file
    session_data = {
        'logged_in': st.session_state.logged_in,
        'login_time': st.session_state.login_time,
        'username': st.session_state.username,
        'role': st.session_state.role,
        'last_activity': st.session_state.last_activity
    }
    save_session(session_id, session_data)

def authenticate(username, password):
    """Authenticate a user against the credentials file"""
    credentials = load_credentials()
    
    if username in credentials:
        user_data = credentials[username]
        salt = user_data["salt"]
        stored_hash = user_data["password"]
        
        # Hash the provided password with the stored salt
        input_hash = hash_password(password, salt)
        
        # Check if the hashes match
        if input_hash == stored_hash:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = user_data["role"]
            st.session_state.login_time = time.time()
            st.session_state.last_activity = time.time()
            
            # Save session data to file
            session_data = {
                'logged_in': st.session_state.logged_in,
                'login_time': st.session_state.login_time,
                'username': st.session_state.username,
                'role': st.session_state.role,
                'last_activity': st.session_state.last_activity
            }
            save_session(session_id, session_data)
            return True
    
    return False

def logout_user(message=None):
    """Log out a user and reset session state"""
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.login_time = None
    st.session_state.last_activity = None
    
    if message:
        st.session_state.logout_message = message
        
    # Clear the persistent session file
    session_dir = setup_session_storage()
    session_file = session_dir / f"{session_id}.pkl"
    if session_file.exists():
        session_file.unlink()

# Check for session timeout on each interaction
session_expired = check_session_timeout()

# Main application logic
def main():
    st.title("Secure Streamlit Application")
    
    # Handle user authentication
    if not st.session_state.logged_in:
        # Show login form
        st.subheader("Login")
        
        # Display logout message if set
        if 'logout_message' in st.session_state and st.session_state.logout_message:
            st.warning(st.session_state.logout_message)
            # Clear the message after showing it
            st.session_state.logout_message = None
        
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Login"):
            if authenticate(username, password):
                st.rerun()
            else:
                st.error("Invalid username or password")
    else:
        # Update activity timestamp
        update_activity()
        
        # Display user information and remaining session time
        st.sidebar.subheader(f"Welcome, {st.session_state.username}")
        st.sidebar.text(f"Role: {st.session_state.role}")
        
        # Calculate and display remaining session time
        if st.session_state.last_activity:
            elapsed = time.time() - st.session_state.last_activity
            remaining = max(0, SESSION_TIMEOUT - elapsed)
            st.sidebar.info(f"Session expires in: {datetime.timedelta(seconds=int(remaining))}")
        
        # Logout button
        if st.sidebar.button("Logout"):
            logout_user("You have been logged out successfully.")
            st.rerun()
        
        # Main content based on user role
        if st.session_state.role == "admin":
            admin_dashboard()
        elif st.session_state.role == "analyst":
            analyst_dashboard()
        else:
            viewer_dashboard()

def admin_dashboard():
    st.header("Admin Dashboard")
    st.write("Welcome to the admin dashboard. You have full access to all features.")
    
    # Admin-specific features here
    st.subheader("User Management")
    st.write("Here you would have controls to add/remove users, change permissions, etc.")
    
    # Add more admin functionality

def analyst_dashboard():
    st.header("Analyst Dashboard")
    st.write("Welcome to the analyst dashboard. You can view and analyze data.")
    
    # Analyst-specific features here
    st.subheader("Data Analysis")
    st.write("Here you would have tools for analyzing data.")
    
    # Add more analyst functionality

def viewer_dashboard():
    st.header("Viewer Dashboard")
    st.write("Welcome to the viewer dashboard. You can view reports and dashboards.")
    
    # Viewer-specific features here
    st.subheader("Reports")
    st.write("Here you would see read-only reports and visualizations.")
    
    # Add more viewer functionality

# Run the main application
if __name__ == "__main__":
    main()
