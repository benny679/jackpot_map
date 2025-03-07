import streamlit as st
import pandas as pd
import json
import hashlib
import os
from datetime import datetime
from utils.auth import check_password, logout, initialize_session_state
from utils.ip_manager import log_ip_activity

# Set page configuration
st.set_page_config(
    page_title="User Management - Jackpot Map",
    page_icon="🎮",
    layout="wide"
)

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

# Initialize session state variables
initialize_session_state()

# Alternative storage using Streamlit session state as a fallback mechanism
def ensure_credentials_in_session():
    """Ensure that credentials are stored in session state (as a temporary fallback)"""
    if "credentials_data" not in st.session_state:
        # Try to load from file first
        credentials = load_credentials_from_file()
        # Store in session state
        st.session_state.credentials_data = credentials

def load_credentials_from_file():
    """Load user credentials from a JSON file."""
    # Get the absolute path to the utils directory
    utils_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "utils")
    credentials_path = os.path.join(utils_dir, "credentials.json")
    
    # Store debug information
    if "debug_info" not in st.session_state:
        st.session_state.debug_info = {}
    
    st.session_state.debug_info["credentials_path"] = credentials_path
    st.session_state.debug_info["load_attempt_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        with open(credentials_path, "r") as f:
            credentials = json.load(f)
            st.session_state.debug_info["load_status"] = "Success"
            st.session_state.debug_info["user_count"] = len(credentials)
            return credentials
    except FileNotFoundError:
        st.session_state.debug_info["load_status"] = "File not found - Creating default"
        
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

        # Ensure the utils directory exists
        try:
            os.makedirs(utils_dir, exist_ok=True)
            
            with open(credentials_path, "w") as f:
                json.dump(default_credentials, f, indent=4)
            
            st.session_state.debug_info["create_status"] = "Success"
            return default_credentials
        except Exception as e:
            st.session_state.debug_info["create_status"] = f"Failed: {str(e)}"
            # Return default credentials anyway
            return default_credentials
    except Exception as e:
        st.session_state.debug_info["load_status"] = f"Error: {str(e)}"
        # Return empty credentials as fallback
        return {}

# Functions for working with credentials - now backed by session state
def load_credentials():
    """Load user credentials with session state fallback."""
    ensure_credentials_in_session()
    return st.session_state.credentials_data

def save_credentials(credentials):
    """Save user credentials to session state and attempt file storage."""
    # Always update session state immediately
    st.session_state.credentials_data = credentials
    
    # Try to save to file as well
    try:
        # Get the absolute path to the utils directory
        utils_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "utils")
        credentials_path = os.path.join(utils_dir, "credentials.json")
        
        # Store debug information
        if "debug_info" not in st.session_state:
            st.session_state.debug_info = {}
        
        st.session_state.debug_info["credentials_path"] = credentials_path
        st.session_state.debug_info["save_attempt_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.debug_info["user_count_to_save"] = len(credentials)
        
        # Ensure the directory exists
        os.makedirs(utils_dir, exist_ok=True)
        
        # Write the file with pretty formatting
        with open(credentials_path, "w") as f:
            json.dump(credentials, f, indent=4)
        
        st.session_state.debug_info["save_status"] = "Success"
        return True
    except Exception as e:
        # Log the error
        st.session_state.debug_info["save_status"] = f"Failed - {str(e)}"
        # Return True anyway since we saved to session state
        return True

# Function to add a new user
def add_user(username, password, role):
    """Add a new user to the credentials."""
    credentials = load_credentials()
    
    # Check if username already exists
    if username in credentials:
        return False, "Username already exists."
    
    # Generate salt and hash password
    salt = secrets.token_hex(16)
    hashed_password = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    
    # Add new user
    credentials[username] = {
        "password": hashed_password,
        "salt": salt,
        "role": role
    }
    
    # Save credentials
    save_credentials(credentials)
    return True, "User added successfully."

# Function to delete a user
def delete_user(username):
    """Delete a user from the credentials."""
    credentials = load_credentials()
    
    # Check if username exists
    if username not in credentials:
        return False, "Username does not exist."
    
    # Prevent deleting the last admin
    admin_count = sum(1 for user, data in credentials.items() if data["role"] == "admin")
    if credentials[username]["role"] == "admin" and admin_count <= 1:
        return False, "Cannot delete the last admin account."
    
    # Delete user
    del credentials[username]
    
    # Save credentials
    save_credentials(credentials)
    return True, "User deleted successfully."

# Function to change user role
def change_role(username, new_role):
    """Change a user's role."""
    credentials = load_credentials()
    
    # Check if username exists
    if username not in credentials:
        return False, "Username does not exist."
    
    # Prevent removing the last admin
    if credentials[username]["role"] == "admin" and new_role != "admin":
        admin_count = sum(1 for user, data in credentials.items() if data["role"] == "admin")
        if admin_count <= 1:
            return False, "Cannot change role for the last admin account."
    
    # Change role
    credentials[username]["role"] = new_role
    
    # Save credentials
    save_credentials(credentials)
    return True, "User role changed successfully."

# Function to reset user password
def reset_password(username, new_password):
    """Reset a user's password."""
    credentials = load_credentials()
    
    # Check if username exists
    if username not in credentials:
        return False, "Username does not exist."
    
    # Generate new salt and hash password
    salt = secrets.token_hex(16)
    hashed_password = hashlib.pbkdf2_hmac(
        'sha256',
        new_password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    
    # Update password
    credentials[username]["password"] = hashed_password
    credentials[username]["salt"] = salt
    
    # Save credentials
    save_credentials(credentials)
    return True, "Password reset successfully."

# Check if the user is authenticated
if check_password():
    # Check if user has admin role
    if st.session_state.get("user_role") != "admin":
        st.error("You don't have permission to access this page.")
        st.stop()
    
    # Log the page view with IP
    if "username" in st.session_state and "ip_address" in st.session_state:
        log_ip_activity(st.session_state["username"], "page_view_user_management", st.session_state["ip_address"])

    # Display logout button in the sidebar
    st.sidebar.button("Logout", on_click=logout)

    # Display user information
    st.sidebar.info(f"Logged in as: {st.session_state['username']} ({st.session_state['user_role']})")
    st.sidebar.info(f"Your IP: {st.session_state['ip_address']}")
    
    # Display storage method information
    st.sidebar.info("Using session state storage with file backup")
    
    # Debug information toggle
    if st.sidebar.checkbox("Show Debug Information"):
        st.sidebar.subheader("Debug Information")
        
        if "debug_info" in st.session_state:
            debug_info = st.session_state.debug_info
            
            st.sidebar.write("**Credentials Path:**")
            st.sidebar.code(debug_info.get("credentials_path", "Not set"))
            
            st.sidebar.write("**File Operations:**")
            cols = st.sidebar.columns(2)
            
            # Load info
            cols[0].write("**Load Status:**")
            load_status = debug_info.get("load_status", "Unknown")
            if "Success" in load_status:
                cols[0].success(load_status)
            elif "Creating" in load_status:
                cols[0].info(load_status)
            else:
                cols[0].error(load_status)
            
            # Save info
            cols[1].write("**Save Status:**")
            save_status = debug_info.get("save_status", "No saves yet")
            if "Success" in save_status:
                cols[1].success(save_status)
            else:
                cols[1].error(save_status)
            
            # User counts
            st.sidebar.write("**User Counts:**")
            cols2 = st.sidebar.columns(2)
            cols2[0].metric("Loaded Users", debug_info.get("user_count", "Unknown"))
            cols2[1].metric("Users in Session", len(st.session_state.get("credentials_data", {})))
            
            # File system check
            st.sidebar.write("**Storage Method:**")
            st.sidebar.success("Session State: Active")
            
            try:
                utils_dir = os.path.dirname(debug_info.get("credentials_path", ""))
                cred_path = debug_info.get("credentials_path", "")
                
                if os.path.exists(cred_path):
                    st.sidebar.success(f"File Backup: Available ({os.path.getsize(cred_path)} bytes)")
                else:
                    st.sidebar.warning("File Backup: Not available")
            except Exception as e:
                st.sidebar.error(f"File Check Error: {str(e)}")
        else:
            st.sidebar.info("No debug information available yet. Try performing an action first.")

    # Main app layout
    st.title("User Management")
    st.write("Manage user accounts and permissions.")

    # Create tabs for different user management functions
    user_tab1, user_tab2, user_tab3, user_tab4 = st.tabs(["User List", "Add User", "Change Role", "Reset Password"])

    with user_tab1:
        st.subheader("User List")
        
        # Load credentials
        credentials = load_credentials()
        
        # Convert to DataFrame for display
        user_data = []
        for username, data in credentials.items():
            user_data.append({
                "Username": username,
                "Role": data["role"]
            })
        
        user_df = pd.DataFrame(user_data)
        st.dataframe(user_df, use_container_width=True)
        
        # Delete user
        st.subheader("Delete User")
        if user_data:
            delete_username = st.selectbox("Select User to Delete", [user["Username"] for user in user_data])
            
            if st.button("Delete User"):
                if delete_username == st.session_state["username"]:
                    st.error("You cannot delete your own account. Please ask another admin to do this.")
                else:
                    success, message = delete_user(delete_username)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
        else:
            st.info("No users available to delete.")

    with user_tab2:
        st.subheader("Add New User")
        
        with st.form("add_user_form"):
            new_username = st.text_input("Username")
            new_password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            new_role = st.selectbox("Role", ["user", "analyst", "admin"])
            
            submit_button = st.form_submit_button("Add User")
            
            if submit_button:
                if not new_username or not new_password:
                    st.error("Username and password are required.")
                elif new_password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    success, message = add_user(new_username, new_password, new_role)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

    with user_tab3:
        st.subheader("Change User Role")
        
        # Load credentials
        credentials = load_credentials()
        
        # Get usernames
        usernames = list(credentials.keys())
        
        if usernames:
            with st.form("change_role_form"):
                username = st.selectbox("Select User", usernames)
                current_role = credentials[username]["role"] if username in credentials else ""
                st.info(f"Current Role: {current_role}")
                new_role = st.selectbox("New Role", ["user", "analyst", "admin"])
                
                submit_button = st.form_submit_button("Change Role")
                
                if submit_button:
                    if new_role == current_role:
                        st.info("No change needed - new role is the same as current role.")
                    else:
                        success, message = change_role(username, new_role)
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
        else:
            st.info("No users available.")

    with user_tab4:
        st.subheader("Reset User Password")
        
        # Load credentials
        credentials = load_credentials()
        
        # Get usernames
        usernames = list(credentials.keys())
        
        if usernames:
            with st.form("reset_password_form"):
                username = st.selectbox("Select User", usernames, key="reset_user")
                new_password = st.text_input("New Password", type="password")
                confirm_password = st.text_input("Confirm New Password", type="password")
                
                submit_button = st.form_submit_button("Reset Password")
                
                if submit_button:
                    if not new_password:
                        st.error("Password is required.")
                    elif new_password != confirm_password:
                        st.error("Passwords do not match.")
                    else:
                        success, message = reset_password(username, new_password)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
        else:
            st.info("No users available.")
else:
    st.warning("Please log in to access user management.")
