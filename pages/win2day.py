import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from matplotlib import style
from scipy.stats import probplot
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pprint import pprint
import json
import hashlib
import os
from datetime import datetime
from utils.auth import check_password, logout, initialize_session_state
from utils.ip_manager import log_ip_activity

# Set page config
st.set_page_config(
    page_title="Original Analysis",
    page_icon="📈",
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

# Title and description
st.title("Original Win2Day Analysis")
st.markdown("This is the original analysis script implemented as a Streamlit page.")

# Set the plotting style
style.use('ggplot')

def analyze_win2day_data():
    """
    Analyzes jackpot data fetched from Google Sheets using gspread
    """
    try:
        # Set up the credentials using Streamlit secrets
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        
        # Get credentials from Streamlit secrets
        service_account_info = st.secrets["gcp_service_account"]
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            service_account_info, scope)
        
        client = gspread.authorize(credentials)

        # Open the Google Sheet (using sheet_id from secrets)
        sheet_id = st.secrets["sheet_id"]
        sheet = client.open_by_key(sheet_id)

        # Select the specific worksheet - note we're using 'Historical Wins' as in the original script
        worksheet = sheet.worksheet('Historical Wins')

        # Get all data from the worksheet
        data = worksheet.get_all_records()

        # Convert to DataFrame
        df = pd.DataFrame(data)

        # Convert date and set as index
        df["Date"] = pd.to_datetime(df["Date Won"])
        df = df.set_index("Date")

        # Print number of unique games
        st.write(f"Number of unique games: {df['Concat'].nunique()}")

        # Let the user select a game to analyze
        game_options = sorted(df['Concat'].unique().tolist())
        default_game = " €€€ Jackpot" if " €€€ Jackpot" in game_options else game_options[0]
        game_to_analyze = st.selectbox("Select Game to Analyze", game_options, index=game_options.index(default_game))
        
        # Filter for selected game
        filtered_df = df[df["Concat"] == game_to_analyze]

        # Clean the Jackpot Win column
        filtered_df["Jackpot Win"] = filtered_df["Jackpot Win"].str.replace("€", "")
        filtered_df["Jackpot Win"] = filtered_df["Jackpot Win"].str.replace(",", "")
        filtered_df["Jackpot Win"] = filtered_df["Jackpot Win"].astype(float)  # Use float instead of int for decimal values

        # Create figure
        fig, ax = plt.subplots(2, 2, figsize=(20, 12))

        # Scatter plot of Jackpot Win over time
        ax[0,1].scatter(filtered_df.index, filtered_df["Jackpot Win"], label="Jackpot Win")
        ax[0,1].set_title(f"{game_to_analyze} Jackpot Win")
        ax[0,1].set_ylabel("Jackpot Win (€)")
        ax[0,1].legend()

        # Plot the histogram of the Jackpot Win
        sns.histplot(filtered_df["Jackpot Win"], bins=20, ax=ax[0,0])
        ax[0,0].set_title(f"{game_to_analyze} Jackpot Win Distribution")
        ax[0,0].set_xlabel("Jackpot Win (€)")
        ax[0,0].set_ylabel("Frequency")
        ax[0,0].legend()

        # Plot of cumulative sum of Jackpot Win over time
        filtered_df = filtered_df.sort_index()  # Ensure data is sorted by date
        filtered_df["Cumulative Jackpot Win"] = filtered_df["Jackpot Win"].cumsum()

        # Use step plot to properly show cumulative growth over time
        ax[1,0].step(filtered_df.index, filtered_df["Cumulative Jackpot Win"], where='post',
                    linewidth=2.5, color='darkred', label="Cumulative Jackpot Win")
        ax[1,0].fill_between(filtered_df.index, filtered_df["Cumulative Jackpot Win"],
                            step="post", alpha=0.4, color='darkred')

        # Highlight individual win points
        ax[1,0].scatter(filtered_df.index, filtered_df["Cumulative Jackpot Win"],
                        color='darkred', s=50, zorder=5)

        ax[1,0].set_title(f"{game_to_analyze} Cumulative Jackpot Win Over Time", fontsize=14)
        ax[1,0].set_ylabel("Cumulative Jackpot Win (€)", fontsize=12)
        ax[1,0].tick_params(axis='x', rotation=45)  # Rotate x-axis labels for better readability
        ax[1,0].grid(axis='y', linestyle='--', alpha=0.7)  # Add horizontal grid lines
        ax[1,0].legend()
        ax[1,0].ticklabel_format(style='plain', axis='y')

        # Plot the probability plot of Jackpot Win
        probplot(filtered_df["Jackpot Win"], plot=ax[1,1])
        ax[1,1].set_title(f"{game_to_analyze} Jackpot Win Probability Plot")

        plt.tight_layout()
        
        # Display the plot in Streamlit
        st.pyplot(fig)
        
        # Add download button for the plot
        buffer = BytesIO()
        fig.savefig(buffer, format='png', dpi=300)
        buffer.seek(0)
        
        st.download_button(
            label="Download Plot as PNG",
            data=buffer,
            file_name=f"{game_to_analyze}_analysis.png",
            mime="image/png"
        )
        
        # Show the data
        with st.expander("View Analysis Data"):
            st.dataframe(filtered_df)
            
            # Add CSV download option
            csv = filtered_df.to_csv().encode('utf-8')
            st.download_button(
                label="Download Data as CSV",
                data=csv,
                file_name=f"{game_to_analyze}_data.csv",
                mime="text/csv",
            )
            
    except Exception as e:
        st.error(f"Error analyzing data: {e}")
        st.info("Make sure you have configured your Streamlit secrets with Google API credentials.")

# Add sidebar options
st.sidebar.header("Analysis Settings")
show_analysis = st.sidebar.button("Run Analysis")

# Add missing import for BytesIO
from io import BytesIO

if show_analysis:
    with st.spinner("Analyzing data..."):
        analyze_win2day_data()
else:
    st.info("Click 'Run Analysis' in the sidebar to generate the plots.")

# Add explanation
with st.expander("About This Analysis"):
    st.markdown("""
    This page runs the original Win2Day analysis script, adapted to work within Streamlit.
    
    Key differences from the standalone script:
    - Uses Streamlit secrets for API credentials instead of a local file
    - Provides an interactive game selection dropdown
    - Displays the plot directly in the web interface
    - Offers download options for both the plot and data
    
    The analysis shows:
    - Distribution of jackpot win amounts
    - Scatter plot of individual jackpot wins over time
    - Cumulative jackpot winnings over time
    - Probability plot to assess normality of win distributions
    """)
