import streamlit as st
import time
import datetime
import json
import hashlib
import os
import pickle
import secrets
import pandas as pd
from pathlib import Path

# =============================================================================
# Core Authentication Functions
# =============================================================================

def hash_password(password, salt):
    """Hash a password with a salt using PBKDF2"""
    return hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000  # 100,000 iterations
    ).hex()

def generate_salt():
    """Generate a random salt"""
    return secrets.token_hex(16)

def load_credentials():
    """Load user credentials from a JSON file."""
    try:
        with open("credentials.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        st.warning("credentials.json file not found. Creating new file.")
        # Create an empty credentials file
        save_credentials({})
        return {}

def save_credentials(credentials):
    """Save user credentials to a JSON file."""
    try:
        with open("credentials.json", "w") as f:
            json.dump(credentials, f, indent=4)
        return True
    except Exception as e:
        st.error(f"Error saving credentials: {e}")
        return False

# =============================================================================
# User Management Functions
# =============================================================================

def add_user(username, password, role):
    """Add a new user to the credentials file."""
    # Load existing credentials
    credentials = load_credentials()
    
    # Check if user already exists
    if username in credentials:
        return False
    
    # Validate role
    valid_roles = ["admin", "analyst", "viewer"]
    if role not in valid_roles:
        return False
    
    # Generate a salt and hash the password
    salt = generate_salt()
    hashed_password = hash_password(password, salt)
    
    # Add the new user
    credentials[username] = {
        "password": hashed_password,
        "salt": salt,
        "role": role,
        "created_at": time.time()
    }
    
    # Save the updated credentials
    return save_credentials(credentials)

def update_user_role(username, new_role):
    """Update a user's role in the credentials file."""
    # Load existing credentials
    credentials = load_credentials()
    
    # Check if user exists
    if username not in credentials:
        return False
    
    # Validate role
    valid_roles = ["admin", "analyst", "viewer"]
    if new_role not in valid_roles:
        return False
    
    # Update the user's role
    credentials[username]["role"] = new_role
    credentials[username]["updated_at"] = time.time()
    
    # Save the updated credentials
    return save_credentials(credentials)

def delete_user(username):
    """Delete a user from the credentials file."""
    # Load existing credentials
    credentials = load_credentials()
    
    # Check if user exists
    if username not in credentials:
        return False
    
    # Delete the user
    del credentials[username]
    
    # Save the updated credentials
    return save_credentials(credentials)

# =============================================================================
# Session Management Functions
# =============================================================================

# Session timeout configuration (in seconds)
SESSION_TIMEOUT = 1800  # 30 minutes

def setup_session_storage():
    """Create session folder and file"""
    session_dir = Path("./.streamlit/sessions")
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir

def save_session(session_id, data):
    """Save session data to file"""
    session_dir = setup_session_storage()
    session_file = session_dir / f"{session_id}.pkl"
    with open(session_file, 'wb') as f:
        pickle.dump(data, f)

def load_session(session_id):
    """Load session data from file"""
    session_dir = setup_session_storage()
    session_file = session_dir / f"{session_id}.pkl"
    if session_file.exists():
        try:
            with open(session_file, 'rb') as f:
                return pickle.load(f)
        except:
            return None
    return None

def get_session_id():
    """Generate a unique session ID based on client info"""
    import socket
    client_ip = socket.gethostbyname(socket.gethostname())
    client_id = hashlib.md5(client_ip.encode()).hexdigest()
    return client_id

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
        salt = user_data.get("salt", "")
        stored_hash = user_data.get("password", "")
        
        # Hash the provided password with the stored salt
        input_hash = hash_password(password, salt)
        
        # Check if the hashes match
        if input_hash == stored_hash:
            # Update last login timestamp
            credentials[username]["last_login"] = time.time()
            save_credentials(credentials)
            
            # Set session state
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = user_data.get("role", "viewer")
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

# =============================================================================
# UI Dashboard Functions
# =============================================================================

def admin_dashboard():
    """Admin dashboard with user management features"""
    st.header("Admin Dashboard")
    st.write("Welcome to the admin dashboard. You have full access to all features.")
    
    # Admin-specific features here
    st.subheader("User Management")
    
    # Create tabs for different user management functions
    user_tabs = st.tabs(["Add User", "List Users", "Update Roles", "Delete User"])
    
    with user_tabs[0]:  # Add User tab
        st.subheader("Add New User")
        
        # Get input for new user
        new_username = st.text_input("Username", key="new_username")
        new_password = st.text_input("Password", type="password", key="new_password")
        new_role = st.selectbox("Role", ["admin", "analyst", "viewer"], key="new_role")
        
        if st.button("Create User"):
            if new_username and new_password:
                # Add user function
                success = add_user(new_username, new_password, new_role)
                if success:
                    st.success(f"User '{new_username}' with role '{new_role}' added successfully!")
                    # Clear the form
                    st.session_state.new_username = ""
                    st.session_state.new_password = ""
                else:
                    st.error(f"Failed to add user '{new_username}'. Username may already exist.")
            else:
                st.warning("Please enter both username and password.")
    
    with user_tabs[1]:  # List Users tab
        st.subheader("Current Users")
        
        # Add a refresh button
        if st.button("Refresh User List"):
            st.rerun()
            
        # Load and display users
        credentials = load_credentials()
        if credentials:
            # Create a dataframe for better display
            users_data = []
            for username, data in credentials.items():
                users_data.append({
                    "Username": username,
                    "Role": data.get("role", "unknown"),
                    "Last Login": datetime.datetime.fromtimestamp(data.get("last_login", 0)).strftime('%Y-%m-%d %H:%M:%S') if data.get("last_login") else "Never"
                })
            
            if users_data:
                users_df = pd.DataFrame(users_data)
                st.dataframe(users_df)
            else:
                st.info("No users found.")
        else:
            st.info("No users found. Add some users to get started.")
    
    with user_tabs[2]:  # Update Roles tab
        st.subheader("Update User Roles")
        
        # Load credentials for user selection
        credentials = load_credentials()
        if credentials:
            usernames = list(credentials.keys())
            
            # Select user to update
            selected_user = st.selectbox("Select User", usernames, key="update_user")
            
            if selected_user:
                current_role = credentials[selected_user].get("role", "viewer")
                new_role = st.selectbox("New Role", ["admin", "analyst", "viewer"], 
                                     index=["admin", "analyst", "viewer"].index(current_role), 
                                     key="update_role")
                
                if st.button("Update Role"):
                    if selected_user and new_role:
                        # Update user role
                        success = update_user_role(selected_user, new_role)
                        if success:
                            st.success(f"User '{selected_user}' role updated to '{new_role}'!")
                        else:
                            st.error(f"Failed to update role for '{selected_user}'.")
        else:
            st.info("No users found. Add some users first.")
            
    with user_tabs[3]:  # Delete User tab
        st.subheader("Delete User")
        
        # Load credentials for user selection
        credentials = load_credentials()
        if credentials:
            usernames = list(credentials.keys())
            
            # Don't allow deleting the current user
            if st.session_state.username in usernames:
                usernames.remove(st.session_state.username)
            
            if usernames:
                selected_user = st.selectbox("Select User to Delete", usernames, key="delete_user")
                
                if st.button("Delete User"):
                    if selected_user:
                        # Confirm deletion
                        st.warning(f"Are you sure you want to delete user '{selected_user}'? This cannot be undone.")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("Yes, Delete User", key="confirm_delete"):
                                # Delete user
                                success = delete_user(selected_user)
                                if success:
                                    st.success(f"User '{selected_user}' deleted successfully!")
                                    st.rerun()
                                else:
                                    st.error(f"Failed to delete user '{selected_user}'.")
                        with col2:
                            if st.button("Cancel"):
                                st.rerun()
            else:
                st.info("No users available to delete.")
        else:
            st.info("No users found. Add some users first.")
            
    # Add other admin features
    st.subheader("System Settings")
    st.write("System configuration options would go here.")
    
    # Debug information
    if st.checkbox("Show Debug Info"):
        st.subheader("Debug Information")
        st.write(f"Current working directory: {os.getcwd()}")
        st.write(f"Credentials file exists: {os.path.exists('credentials.json')}")
        
        # Test write permissions
        try:
            test_file = "test_write_permission.txt"
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            st.write("Write permission: OK")
        except Exception as e:
            st.write(f"Write permission error: {e}")

def analyst_dashboard():
    """Analyst dashboard with data analysis features"""
    st.header("Analyst Dashboard")
    st.write("Welcome to the analyst dashboard. You can view and analyze data.")
    
    # Analyst-specific features here
    st.subheader("Data Analysis")
    
    # Sample data visualization
    chart_data = pd.DataFrame({
        'date': pd.date_range(start='2023-01-01', periods=10),
        'sales': [10, 20, 15, 25, 30, 20, 15, 35, 40, 30]
    })
    
    st.line_chart(chart_data.set_index('date'))
    
    # Add more analyst functionality
    st.write("More data analysis tools would go here.")

def viewer_dashboard():
    """Viewer dashboard with read-only reports"""
    st.header("Viewer Dashboard")
    st.write("Welcome to the viewer dashboard. You can view reports and dashboards.")
    
    # Viewer-specific features here
    st.subheader("Reports")
    
    # Sample report
    st.write("Sample Monthly Report")
    report_data = pd.DataFrame({
        'Month': ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
        'Revenue': [15000, 16200, 17500, 19000, 20500],
        'Expenses': [12000, 12500, 13000, 13200, 14000],
        'Profit': [3000, 3700, 4500, 5800, 6500]
    })
    
    st.table(report_data)
    
    # Add more viewer functionality
    st.write("More reports would be available here.")

# =============================================================================
# Main Application
# =============================================================================

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

def main():
    """Main application logic"""
    st.title("Secure Streamlit Application")
    
    # Check for session timeout
    session_expired = check_session_timeout()
    
    # Handle user authentication
    if not st.session_state.logged_in:
        # Show login form
        st.subheader("Login")
        
        # Display logout message if set
        if 'logout_message' in st.session_state and st.session_state.logout_message:
            st.warning(st.session_state.logout_message)
            # Clear the message after showing it
            st.session_state.logout_message = None
        
        # First-time setup - create an admin user if no users exist
        credentials = load_credentials()
        if not credentials:
            st.info("No users found. Creating default admin user.")
            if add_user("admin", "admin", "admin"):
                st.success("Default admin user created. Username: admin, Password: admin")
                st.warning("Please change the default password after logging in!")
        
        # Login form
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

# Run the main application
if __name__ == "__main__":
    main()
