import streamlit as st
import pandas as pd
import json
import os
import time
from datetime import datetime
from utils.auth import check_password, logout, initialize_session_state
from utils.ip_manager import log_ip_activity

# Set page configuration
st.set_page_config(
    page_title="Admin Panel - Jackpot Map",
    page_icon="🎮",
    layout="wide"
)

# Initialize session state variables
initialize_session_state()

# Check if the user is authenticated
if check_password():
    # Check if user has admin role
    if st.session_state.get("user_role") != "admin":
        st.error("You don't have permission to access this page.")
        st.stop()
    
    # Log the page view with IP
    if "username" in st.session_state and "ip_address" in st.session_state:
        log_ip_activity(st.session_state["username"], "page_view_admin", st.session_state["ip_address"])

    # Display logout button in the sidebar
    st.sidebar.button("Logout", on_click=logout)

    # Display user information
    st.sidebar.info(f"Logged in as: {st.session_state['username']} ({st.session_state['user_role']})")
    st.sidebar.info(f"Your IP: {st.session_state['ip_address']}")

    # Main app layout
    st.title("Admin Panel")
    st.write("Manage user activity, IP settings, and system logs.")

    # Create tabs for different admin functions
    admin_tab1, admin_tab2, admin_tab3 = st.tabs(["User Activity", "IP Management", "System Logs"])

    with admin_tab1:
        # Show recent login activity
        st.subheader("User Login Activity")
        
        if os.path.exists("logs/login_activity.csv"):
            login_activity = pd.read_csv("logs/login_activity.csv")

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
        else:
            st.info("No login activity logs found.")

    with admin_tab2:
        st.subheader("IP Address Management")

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
        st.write("Configure IP access control settings")

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
        else:
            st.info("No IP activity logs found.")

    with admin_tab3:
        st.subheader("System Logs")

        # Show rate limiting information
        st.write("Rate Limiting Status")

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

            if rate_limit_data:
                rate_limit_df = pd.DataFrame(rate_limit_data)
                st.dataframe(rate_limit_df, use_container_width=True)

                # Button to clear rate limits
                if st.button("Clear All Rate Limits"):
                    with open("logs/rate_limits.json", "w") as f:
                        json.dump({}, f)
                    st.success("Rate limits cleared successfully!")
                    st.experimental_rerun()
            else:
                st.info("No rate limits currently active.")
        else:
            st.info("No rate limiting data found.")
else:
    st.warning("Please log in to access the admin panel.")
