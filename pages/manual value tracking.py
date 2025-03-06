import streamlit as st
import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from datetime import datetime, timedelta, date
import io
import os
import tempfile

from utils.auth import check_password, logout, initialize_session_state
from utils.ip_manager import log_ip_activity
from utils.data_loader import upload_to_slack

# Set environment variables from secrets for the entire application
if 'slack' in st.secrets:
    os.environ['SLACK_TOKEN'] = st.secrets.slack.slack_token
    os.environ['SLACK_CHANNEL_ID'] = st.secrets.slack.channel_id

# Set page configuration
st.set_page_config(
    page_title="Manual Value Tracking - Jackpot Map",
    page_icon="📊",
    layout="wide"
)

# Initialize session state variables
initialize_session_state()

# Initialize additional session state variables
if 'plot_generated' not in st.session_state:
    st.session_state.plot_generated = False
if 'current_plot' not in st.session_state:
    st.session_state.current_plot = None
if 'interactive_charts' not in st.session_state:
    st.session_state.interactive_charts = None
if 'plot_settings' not in st.session_state:
    st.session_state.plot_settings = {
        'casino': None,
        'game': None,
        'region': None,
        'start_date': None,
        'end_date': None
    }
if 'plot_type' not in st.session_state:
    st.session_state.plot_type = "Matplotlib"

# Function to load manual tracking data from Google Sheet
@st.cache_data(ttl=3600)  # Cache data for 1 hour
def load_manual_tracking_data():
    """Load manual tracking data from Google Sheets."""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        client = gspread.authorize(creds)
        
        # Open the specific sheet
        sheet = client.open("Research - Ops")
        worksheet = sheet.worksheet("Daily Value Tracking")
        records = worksheet.get_all_records()
        
        # Convert to DataFrame
        df = pd.DataFrame.from_records(records)
        
        # Preprocess data
        if not df.empty:
            # Fill missing values and clean time format
            df["Time"] = df["Time"].fillna("00:00").astype(str).str.replace(".", ":")
            
            # Replace invalid time formats with 00:00
            df.loc[~df["Time"].str.match(r"\d{2}:\d{2}").fillna(False), "Time"] = "00:00"
            
            # Create datetime column - try multiple date formats
            try:
                df["DateTime"] = pd.to_datetime(
                    df["Date"] + " " + df["Time"], 
                    format="%d-%m-%Y %H:%M", 
                    errors='coerce'
                )
            except:
                try:
                    # Try alternative format
                    df["DateTime"] = pd.to_datetime(
                        df["Date"] + " " + df["Time"], 
                        format="%Y-%m-%d %H:%M", 
                        errors='coerce'
                    )
                except:
                    # Last resort - let pandas infer format
                    df["DateTime"] = pd.to_datetime(
                        df["Date"] + " " + df["Time"], 
                        errors='coerce'
                    )
            
            # Drop rows with missing dates
            df.dropna(subset=["DateTime"], inplace=True)
            
            # Convert level columns to numeric
            level_columns = [col for col in df.columns if col.startswith("Level ")]
            for col in level_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    except Exception as e:
        st.error(f"Error loading manual tracking data: {str(e)}")
        return pd.DataFrame()

def create_matplotlib_plot(filtered_df, level_columns, casino, game, region):
    """Create a Matplotlib plot of level data."""
    # Set datetime as index for proper time-series plotting
    plot_df = filtered_df.set_index("DateTime").copy()
    
    num_levels = len(level_columns)
    
    # Set up the figure
    cols = min(2, num_levels)  # Maximum 2 columns
    rows = (num_levels + cols - 1) // cols
    
    fig, axs = plt.subplots(rows, cols, figsize=(15, 5 * rows), constrained_layout=True)
    
    # Handle single subplot case
    if num_levels == 1:
        axs = np.array([[axs]])
    elif rows == 1 and cols > 1:
        axs = axs.reshape(1, -1)
    
    # Plot each level
    for i, level in enumerate(level_columns):
        row, col = divmod(i, cols)
        
        # Handle case where axs is a single subplot
        if num_levels == 1:
            ax = axs[0, 0]
        else:
            ax = axs[row, col]
        
        ax.plot(plot_df.index, plot_df[level], marker='o', linestyle='-', label=level)
        ax.set_title(f"{casino} - {game} - {level}")
        ax.set_xlabel("Date")
        ax.set_ylabel("Value")
        ax.tick_params(axis='x', rotation=45)
        ax.legend()
        ax.grid(True)
    
    # Hide any unused subplots
    if num_levels > 1 and num_levels % cols != 0:
        for j in range(num_levels % cols, cols):
            if rows > 1 or cols > 1:  # Only if we have multiple subplots
                fig.delaxes(axs[rows-1, j])
    
    plt.tight_layout()
    return fig

def create_streamlit_charts(filtered_df, level_columns, casino, game, region):
    """Create interactive charts using Streamlit's native chart functionality."""
    # Set datetime as index for proper time-series plotting
    plot_df = filtered_df.set_index("DateTime").copy()
    
    # Fill NaN values with 0 for display
    plot_df = plot_df.fillna(0)
    
    # Create a dictionary to store chart renderers
    chart_renderers = {}
    
    # Create a chart for each level
    for level in level_columns:
        # Create a dataframe with just this level
        level_df = plot_df[[level]]
        
        # Store a function that will render this chart
        chart_renderers[level] = (level_df, f"{casino} - {game} - {level}")
    
    return chart_renderers

# Main app code
def main():
    # Check if the user is authenticated
    if check_password():
        # Log the page view with IP
        if "username" in st.session_state and "ip_address" in st.session_state:
            log_ip_activity(st.session_state["username"], "page_view_manual_tracking", st.session_state["ip_address"])

        # Display logout button in the sidebar
        st.sidebar.button("Logout", on_click=logout)

        # Display user information
        st.sidebar.info(f"Logged in as: {st.session_state['username']} ({st.session_state['user_role']})")

        # Display IP address (only for admins)
        if st.session_state.get("user_role") == "admin":
            st.sidebar.info(f"Your IP: {st.session_state['ip_address']}")

        # Main app layout
        st.title("📊 Manual Value Tracking")
        st.write("Filter and visualize manual tracking data for casinos, games, and regions.")
        
        # Load manual tracking data
        with st.spinner("Loading manual tracking data from Google Sheets..."):
            df = load_manual_tracking_data()
            
        if df.empty:
            st.error("Failed to load manual tracking data. Please check your connection to Google Sheets.")
            st.stop()
        
        # Sidebar filters
        st.sidebar.header("Filters")
        
        # Add a plot type selector to the sidebar
        plot_type = st.sidebar.radio(
            "Chart Type",
            ["Matplotlib", "Interactive"],
            index=0,
            help="Select the chart type to visualize your data"
        )

        # Store the plot type in session state
        st.session_state.plot_type = plot_type
            
        # Date range selection
        st.sidebar.subheader("Date Range")
        
        # Casino filter
        casinos = sorted(df["Casino"].unique())
        selected_casino = st.sidebar.selectbox("Select Casino", casinos)
        
        # Filter dataframe based on selected casino
        casino_df = df[df["Casino"] == selected_casino]
        
        # Region filter - depends on selected casino
        regions = sorted(casino_df["Region"].unique())
        selected_region = st.sidebar.selectbox("Select Region", regions)
        
        # Filter dataframe based on selected region
        region_df = casino_df[casino_df["Region"] == selected_region]
        
        # Game filter - depends on selected casino and region
        games = sorted(region_df["Game"].unique())
        selected_game = st.sidebar.selectbox("Select Game", games)
        
        # Get min and max dates from the data
        min_date = df["DateTime"].min().date() if not df.empty else date.today() - timedelta(days=30)
        max_date = df["DateTime"].max().date() if not df.empty else date.today()
        
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input(
                "Start date",
                value=min_date,
                min_value=min_date,
                max_value=max_date
            )
        with col2:
            end_date = st.date_input(
                "End date",
                value=max_date,
                min_value=min_date,
                max_value=max_date
            )
        
        # Convert to datetime
        start_datetime = pd.to_datetime(start_date)
        end_datetime = pd.to_datetime(end_date) + timedelta(days=1) - timedelta(seconds=1)  # End of day
        
        # Display the plot
        generate_plot = st.button("Generate Plot")
        
        # Check if we should generate a new plot or use stored one
        if generate_plot:
            # Filter data based on selection
            filtered_df = df[
                (df["Casino"] == selected_casino) &
                (df["Game"] == selected_game) &
                (df["Region"] == selected_region) &
                (df["DateTime"] >= start_datetime) &
                (df["DateTime"] <= end_datetime)
            ].copy()
            
            if filtered_df.empty:
                st.warning("No data available for the selected criteria.")
            else:
                # Get level columns
                level_columns = [col for col in filtered_df.columns if col.startswith("Level ")]
                
                if not level_columns:
                    st.warning("No level data found for the selected criteria.")
                else:
                    # Store current settings
                    st.session_state.plot_settings = {
                        'casino': selected_casino,
                        'game': selected_game,
                        'region': selected_region,
                        'start_date': start_datetime,
                        'end_date': end_datetime
                    }
                    
                    # Generate and store the plot
                    st.session_state.current_plot = create_matplotlib_plot(
                        filtered_df, 
                        level_columns, 
                        selected_casino, 
                        selected_game, 
                        selected_region
                    )
                    
                    # Generate and store interactive charts
                    st.session_state.interactive_charts = create_streamlit_charts(
                        filtered_df, 
                        level_columns, 
                        selected_casino, 
                        selected_game, 
                        selected_region
                    )
                    
                    st.session_state.plot_generated = True
        
        # Display plot if available
        if st.session_state.plot_generated:
            st.subheader(f"Level Values for {st.session_state.plot_settings['casino']} - {st.session_state.plot_settings['game']} - {st.session_state.plot_settings['region']}")
            
            try:
                if st.session_state.plot_type == "Matplotlib" and st.session_state.current_plot is not None:
                    # Display the Matplotlib plot
                    st.pyplot(st.session_state.current_plot)
                elif st.session_state.plot_type == "Interactive" and st.session_state.interactive_charts is not None:
                    # Display interactive charts
                    for level, (level_df, title) in st.session_state.interactive_charts.items():
                        st.subheader(title)
                        st.line_chart(level_df, use_container_width=True)
                        st.write("---")  # Add a separator between charts
            except Exception as e:
                st.error(f"Error displaying chart: {str(e)}")
                
            # Debug Slack settings - show only if the plot is already generated
            debug_slack = st.checkbox("Debug Slack Settings")
            if debug_slack:
                st.write("Slack configuration debug information:")
                
                # Check if slack config exists in secrets
                if 'slack' in st.secrets:
                    st.write("✅ Slack section found in secrets")
                    st.write("- Token status:", "Available" if st.secrets.slack.get("slack_token") else "Missing")
                    st.write("- Channel status:", "Available" if st.secrets.slack.get("channel_id") else "Missing")
                    
                    # Check environment variables
                    st.write("Environment variables:")
                    st.write("- SLACK_TOKEN:", "Set" if os.environ.get('SLACK_TOKEN') else "Not set")
                    st.write("- SLACK_CHANNEL_ID:", "Set" if os.environ.get('SLACK_CHANNEL_ID') else "Not set")
                else:
                    st.write("❌ No slack section found in secrets.toml")
            
            # Sharing options
            st.subheader("Share Plot")
            col1, col2 = st.columns([3, 1])
            
            with col1:
                slack_message = st.text_input(
                    "Slack message (optional)",
                    value=f"Manual Tracking Plot: {st.session_state.plot_settings['casino']} - {st.session_state.plot_settings['game']} - {st.session_state.plot_settings['region']}"
                )
            
            with col2:
                # Save image functionality - only available for Matplotlib
                if st.button("Export to Slack"):
                    try:
                        # Create temp file with proper extension
                        temp_dir = tempfile.gettempdir()
                        plot_file = os.path.join(temp_dir, "manual_tracking_plot.png")
                        
                        # Save the matplotlib plot (always use matplotlib for export)
                        if st.session_state.current_plot is not None:
                            st.session_state.current_plot.savefig(
                                plot_file,
                                bbox_inches='tight',
                                dpi=300,
                                facecolor='white',
                                edgecolor='none'
                            )
                            
                            st.info(f"Sending plot to Slack channel...")
                            
                            # Set environment variables explicitly before upload
                            if 'slack' in st.secrets:
                                os.environ['SLACK_TOKEN'] = st.secrets.slack.slack_token
                                os.environ['SLACK_CHANNEL_ID'] = st.secrets.slack.channel_id
                            
                            # Print info about the file being uploaded
                            if os.path.exists(plot_file):
                                st.write(f"File exists with size: {os.path.getsize(plot_file)} bytes")
                            else:
                                st.error(f"File was not created properly at {plot_file}")
                                return
                            
                            # Upload to Slack with detailed error handling
                            try:
                                upload_success = upload_to_slack(plot_file, slack_message)
                                if upload_success:
                                    st.success("Plot uploaded to Slack successfully!")
                                else:
                                    st.error("Failed to upload plot to Slack. Check debug info for details.")
                            except Exception as e:
                                st.error(f"Error during Slack upload: {str(e)}")
                        else:
                            st.error("No Matplotlib plot available to export.")
                    except Exception as e:
                        st.error(f"Error preparing plot for upload: {str(e)}")
            
            # Add download option for the plot - only available for Matplotlib
            try:
                if st.session_state.current_plot is not None:
                    buf = io.BytesIO()
                    st.session_state.current_plot.savefig(buf, format="png", bbox_inches='tight', dpi=300)
                    buf.seek(0)
                    
                    st.download_button(
                        label="Download Plot as PNG",
                        data=buf,
                        file_name=f"manual_tracking_{st.session_state.plot_settings['casino']}_{st.session_state.plot_settings['game']}_{st.session_state.plot_settings['region']}.png",
                        mime="image/png"
                    )
            except Exception as e:
                st.error(f"Error preparing download: {str(e)}")
        
        # Display raw data based on session state if plot is generated, otherwise use current filters
        st.subheader("Raw Data")
        
        if st.session_state.plot_generated:
            # Use stored settings from when plot was generated
            settings = st.session_state.plot_settings
            filtered_df = df[
                (df["Casino"] == settings['casino']) &
                (df["Game"] == settings['game']) &
                (df["Region"] == settings['region']) &
                (df["DateTime"] >= settings['start_date']) &
                (df["DateTime"] <= settings['end_date'])
            ].copy()
        else:
            # Use current filter settings
            filtered_df = df[
                (df["Casino"] == selected_casino) &
                (df["Game"] == selected_game) &
                (df["Region"] == selected_region) &
                (df["DateTime"] >= start_datetime) &
                (df["DateTime"] <= end_datetime)
            ].copy()
        
        # Sort by datetime
        filtered_df = filtered_df.sort_values("DateTime", ascending=False)
        
        # Format columns for display
        if not filtered_df.empty:
            display_df = filtered_df.copy()
            display_df["DateTime"] = display_df["DateTime"].dt.strftime("%Y-%m-%d %H:%M")
            
            # Select columns to display
            level_columns = [col for col in display_df.columns if col.startswith("Level ")]
            display_columns = ["DateTime", "Casino", "Game", "Region"] + level_columns
            
            st.dataframe(
                display_df[display_columns], 
                use_container_width=True
            )
            
            # Download option
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download CSV",
                csv,
                f"manual_tracking_{selected_casino}_{selected_game}_{selected_region}.csv",
                "text/csv",
                key='download-csv'
            )
        else:
            st.warning("No data available for the selected criteria.")
            
    else:
        st.warning("Please log in to access the manual tracking data.")

if __name__ == "__main__":
    main()
