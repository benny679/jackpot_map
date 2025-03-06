import streamlit as st
import pandas as pd
from utils.auth import check_password, logout, initialize_session_state
from utils.ip_manager import log_ip_activity
from utils.data_loader import load_sheet_data, upload_to_slack
from datetime import datetime
import os

# Set page configuration
st.set_page_config(
    page_title="Dashboard - Jackpot Map",
    page_icon="🎮",
    layout="wide"
)

# Initialize session state variables
initialize_session_state()

# Check if the user is authenticated
if check_password():
    # Log the page view with IP
    if "username" in st.session_state and "ip_address" in st.session_state:
        log_ip_activity(st.session_state["username"], "page_view_dashboard", st.session_state["ip_address"])

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
                if os.environ.get('SLACK_TOKEN'):
                    file_path = "jackpot_map_filtered.csv"
                    filtered_df.to_csv(file_path, index=False)
                    upload_to_slack(file_path, slack_message)
                else:
                    st.warning("Slack token not set. Please set the SLACK_TOKEN environment variable.")

    # Footer with information
    st.markdown("---")
    st.markdown("Dashboard updates hourly from Google Sheets. Last update: " + pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"))
else:
    st.warning("Please log in to access the dashboard.")
