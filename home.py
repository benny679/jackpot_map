import streamlit as st
import pandas as pd
from datetime import datetime
from utils.auth import check_password, logout, initialize_session_state
from utils.ip_manager import log_ip_activity

# Set page configuration
st.set_page_config(
    page_title="Jackpot Map Dashboard",
    page_icon="🎮",
    layout="wide"
)

# Initialize session state variables
initialize_session_state()

# Main app layout
st.title("🎮 Jackpot Map Dashboard")
st.write("Dashboard for RNG Research related stuff")
st.write("Message Ben for a log-in and permissions")

# Check if the user is authenticated
if check_password():
    # Log the page view with IP
    if "username" in st.session_state and "ip_address" in st.session_state:
        log_ip_activity(st.session_state["username"], "page_view_home", st.session_state["ip_address"])

    # Display logout button in the sidebar
    st.sidebar.button("Logout", on_click=logout)

    # Display user information
    st.sidebar.info(f"Logged in as: {st.session_state['username']} ({st.session_state['user_role']})")

    # Display IP address (only for admins)
    if st.session_state["user_role"] == "admin":
        st.sidebar.info(f"Your IP: {st.session_state['ip_address']}")

    # Home page content
    st.subheader("Navigation")
    st.write("""
    Use the sidebar to navigate to different sections of the dashboard:
    
    - **Dashboard**: View and filter the jackpot map data
    - **Admin Panel**: (Admin only) View login activity and manage IP settings
    - **User Management**: (Admin only) Manage user accounts and permissions
    - **Manual Value Tracking**: Jackpots that are being tracked manually via Research Ops Daily Value Tracking
    - **KPIs**: Check how poorly or how well some parts of the RNG project are doing, purely for bragging rights and shit talking
    """)

    # Show some quick stats
    st.subheader("Quick Information")
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(f"Last login: {st.session_state.get('login_time', 'Unknown')}")
    
    with col2:
        st.info(f"Today's date: {datetime.now().strftime('%Y-%m-%d')}")

    # Footer
    st.markdown("---")
    st.markdown("Jackpot Map Dashboard v2.0 | Multi-page Version")
