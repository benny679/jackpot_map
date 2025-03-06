import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import style
from matplotlib.ticker import ScalarFormatter
from datetime import datetime, timedelta
import requests
import json
import logging
from urllib3.exceptions import InsecureRequestWarning
import warnings
import seaborn as sns
from scipy import stats
import io
from PIL import Image

# Import shared utilities
from utils.auth import check_password, logout
from utils.ip_utils import log_ip_activity

# Suppress insecure HTTPS warnings
warnings.filterwarnings('ignore', category=InsecureRequestWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set page config
st.set_page_config(
    page_title="Jackpot Analysis - Jackpot Map",
    page_icon="📈",
    layout="wide"
)

# Check authentication before showing content
if not st.session_state.get("authenticated", False):
    st.error("Please login from the home page to access this page.")
    st.stop()

# Check if user has proper permissions
if st.session_state.get("user_role") not in ["admin", "analyst"]:
    st.error("You don't have permission to access the jackpot analysis features.")
    st.info("This page is restricted to administrators and analysts only.")
    st.stop()

# Log page view
if "username" in st.session_state and "ip_address" in st.session_state:
    log_ip_activity(st.session_state["username"], "jackpot_analysis_view", st.session_state["ip_address"])

# Display logout button in the sidebar
st.sidebar.button("Logout", on_click=logout)

# Display user information
st.sidebar.info(f"Logged in as: {st.session_state['username']} ({st.session_state['user_role']})")

# Main app layout
st.title("📈 Jackpot Analysis")
st.write("Analyze jackpot data and visualize trends.")

class JackpotAPI:
    def __init__(self, base_url: str = "https://grnst-data-store-serv.com"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.verify = False

    def test_connection(self) -> bool:
        try:
            with st.spinner("Testing API connection..."):
                response = self.session.get(self.base_url)
                response.raise_for_status()
                st.success("API connection test successful")
                return True
        except requests.exceptions.RequestException as e:
            st.error(f"API connection test failed: {str(e)}")
            return False

    def get_timeseries(
        self,
        jackpot_id: str,
        days: int = None,
        return_df: bool = True
    ):
        """
        Fetch jackpot timeseries data.

        Args:
            jackpot_id: Identifier for the jackpot
            days: Number of days of data to fetch (optional)
            return_df: If True, returns pandas DataFrame, else raw JSON
        """
        endpoint = f"{self.base_url}/api/timeseries"

        # First try without timespan
        payload = {"jackpot_id": jackpot_id}
        
        with st.spinner(f"Fetching data for jackpot {jackpot_id}..."):
            st.info("Trying request without timespan first...")

            try:
                response = self.session.post(endpoint, json=payload)
                response.raise_for_status()
                data = response.json()

                # If we got no data and days parameter was provided, try with timespan
                if len(data.get("timeseriesData", [])) == 0 and days is not None:
                    st.info(f"No data received, trying with {days} days timespan...")
                    timespan_ms = days * 24 * 60 * 60 * 1000
                    payload["timespan"] = timespan_ms

                    response = self.session.post(endpoint, json=payload)
                    response.raise_for_status()
                    data = response.json()

                if return_df:
                    df = pd.DataFrame(data.get("timeseriesData", []), columns=['ts', 'amount'])
                    if not df.empty:
                        # Ensure amount is numeric
                        df['amount'] = pd.to_numeric(df['amount'])
                        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
                        st.success(f"Successfully fetched {len(df)} data points")
                    return df
                return data

            except requests.exceptions.RequestException as e:
                st.error(f"Failed to fetch timeseries data: {str(e)}")
                return pd.DataFrame() if return_df else {}
            except (KeyError, ValueError) as e:
                st.error(f"Failed to process timeseries data: {str(e)}")
                return pd.DataFrame() if return_df else {}

def analyze_jackpot(jackpot_id: str, days: int = None):
    """
    Analyze and plot jackpot data.

    Args:
        jackpot_id: Identifier for the jackpot
        days: Optional number of days of data to analyze
    """
    api = JackpotAPI()

    if not api.test_connection():
        st.error("Failed to connect to API")
        return

    # Fetch the data
    ts_data = api.get_timeseries(
        jackpot_id=jackpot_id,
        days=days,
        return_df=True
    )

    if ts_data.empty:
        period = f" over the last {days} days" if days else ""
        st.error(f"No data received for jackpot {jackpot_id}{period}")
        return

    # Show raw data in an expander
    with st.expander("View Raw Data"):
        st.dataframe(ts_data)

    # Create the visualizations
    st.subheader("Jackpot Analysis Visualizations")
    
    # filter for specific start date if data goes back far enough
    min_date = ts_data['ts'].min().date()
    max_date = ts_data['ts'].max().date()
    
    # Date range selector
    date_range = st.date_input(
        "Select date range for analysis",
        value=[min_date, max_date],
        min_value=min_date,
        max_value=max_date
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        # Convert date to datetime for filtering
        start_datetime = pd.Timestamp(start_date)
        end_datetime = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        
        # Filter data based on date range
        ts_data = ts_data[(ts_data['ts'] >= start_datetime) & (ts_data['ts'] <= end_datetime)]
    
    # Calculate differences and identify significant drops
    ts_data['diff'] = ts_data['amount'].diff()
    ts_data['diff_pct'] = ts_data['amount'].pct_change()
    
    # Allow user to adjust the threshold for significant drops
    drop_threshold = st.slider(
        "Significant drop threshold (%)", 
        min_value=1, 
        max_value=25, 
        value=10,
        help="Define what percentage decrease is considered a significant drop"
    )
    
    ts_data['significant_drop'] = ts_data['diff_pct'] < -drop_threshold/100
    previous_values = ts_data['amount'].shift(1)
    ts_data['previous_amount'] = previous_values

    # Filter for significant drops
    significant_drops = ts_data[ts_data['significant_drop']]
    
    if significant_drops.empty:
        st.warning(f"No significant drops found with the current threshold ({drop_threshold}%).")
        return
    
    significant_drops['previous_amount'] = previous_values[ts_data['significant_drop']]

    # Calculate average drop
    average_drop = significant_drops['previous_amount'].mean()
    
    # Create tabs for different visualizations
    tab1, tab2, tab3, tab4 = st.tabs([
        "Jackpot Over Time", 
        "Significant Drops Histogram", 
        "Probability Plot",
        "Cumulative Drops"
    ])
    
    with tab1:
        # Jackpot over time plot
        st.subheader("Jackpot Value Over Time")
        
        # Create matplotlib figure
        fig, ax = plt.subplots(figsize=(12, 6))
        style.use('ggplot')
        
        # Plot the data
        ax.plot(ts_data['ts'], ts_data['amount'], linewidth=1.5)
        ax.scatter(significant_drops['ts'], significant_drops['amount'], color='red', label='Significant Drop')
        
        # Add average drop line
        ax.axhline(y=average_drop, color='r', linestyle='--', label=f'Average Drop: {average_drop:.2f}')
        
        # Annotate the previous value of significant drops
        for index, row in significant_drops.iterrows():
            ax.annotate(
                f"{row['previous_amount']:.2f}", 
                (row['ts'], row['previous_amount']), 
                textcoords="offset points", 
                xytext=(0,10), 
                ha='center'
            )
        
        # Set title and labels
        ax.set_title(f"{jackpot_id} Jackpot Over Time")
        ax.set_xlabel("Time")
        ax.set_ylabel("Amount")
        ax.legend()
        
        # Format axes
        ax.yaxis.set_major_formatter(ScalarFormatter())
        plt.ticklabel_format(style='plain', axis='y')
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Display in Streamlit
        st.pyplot(fig)
        
        # Summary statistics
        st.subheader("Summary Statistics")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Average Drop Amount", f"{average_drop:.2f}")
        
        with col2:
            total_drops = len(significant_drops)
            st.metric("Total Significant Drops", f"{total_drops}")
        
        with col3:
            days_span = (ts_data['ts'].max() - ts_data['ts'].min()).days
            drops_per_day = total_drops / max(1, days_span)
            st.metric("Drops per Day", f"{drops_per_day:.2f}")
    
    with tab2:
        # Histogram of significant drops
        st.subheader("Significant Drops Histogram")
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        sns.histplot(significant_drops['previous_amount'], kde=True, ax=ax, color='#8E44AD', bins=30)
        ax.set_ylabel('Frequency')
        ax.set_xlabel('Amount')
        ax.set_title('Distribution of Significant Drops')
        
        # x axis locator and formatter
        ax.xaxis.set_major_locator(plt.MaxNLocator(25))
        ax.xaxis.set_major_formatter(ScalarFormatter())
        
        st.pyplot(fig)
        
        # Summary statistics for the histogram
        st.subheader("Drop Amount Statistics")
        
        stats_df = pd.DataFrame({
            'Statistic': ['Min', 'Max', 'Mean', 'Median', 'Std Dev'],
            'Value': [
                significant_drops['previous_amount'].min(),
                significant_drops['previous_amount'].max(),
                significant_drops['previous_amount'].mean(),
                significant_drops['previous_amount'].median(),
                significant_drops['previous_amount'].std()
            ]
        })
        
        st.table(stats_df)
    
    with tab3:
        # Probability plot
        st.subheader("Probability Plot of Significant Drops")
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot probability plot
        stats.probplot(significant_drops['previous_amount'], plot=ax)
        ax.set_title('Significant Drops Probability Plot')
        
        st.pyplot(fig)
        
        # Explanation
        st.info("""
        The probability plot shows how well the drop amounts follow a normal distribution. 
        Points that follow the straight line indicate normal distribution. 
        Deviations suggest the data may follow a different distribution.
        """)
    
    with tab4:
        # Cumulative drops plot
        st.subheader("Cumulative Drops Over Time")
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Calculate cumulative daily wins
        cumulative_daily_wins = significant_drops['previous_amount'].cumsum()
        # Get the dates for each significant drop
        cumulative_daily_wins.index = significant_drops['ts']
        
        ax.bar(
            cumulative_daily_wins.index, 
            cumulative_daily_wins.values,
            edgecolor='black', 
            color='g'
        )
        
        # Thicken the bars
        [i.set_linewidth(2) for i in ax.patches]
        
        ax.set_title('Cumulative Drop Amounts')
        ax.set_xlabel('Date')
        ax.set_ylabel('Cumulative Amount')
        ax.tick_params(axis='x', rotation=45)
        ax.xaxis.set_major_locator(plt.MaxNLocator(10))
        ax.yaxis.set_major_formatter(ScalarFormatter())
        ax.ticklabel_format(axis='y', style='plain')
        
        plt.tight_layout()
        st.pyplot(fig)
        
        # Growth calculations
        start_value = ts_data['amount'].iloc[0]
        end_value = ts_data['amount'].iloc[-1]
        days_span = (ts_data['ts'].iloc[-1] - ts_data['ts'].iloc[0]).days or 1  # Avoid division by zero
        
        growth = (end_value - start_value) / days_span
        
        st.metric(
            "Daily Growth Rate (excluding drops)", 
            f"{growth:.2f}",
            delta=f"{(growth/start_value*100):.2f}%" if start_value else "N/A"
        )

# Sidebar inputs
st.sidebar.subheader("Analysis Parameters")

# Jackpot ID input
jackpot_id = st.sidebar.text_input(
    "Jackpot ID",
    value="feed-skillonnet.redtiger.cash_skillOnNet-Mega Jackpot_38002",
    help="Enter the unique identifier for the jackpot"
)

# Days input
days_options = [7, 14, 30, 60, 90, "All"]
days_selection = st.sidebar.selectbox(
    "Data Timespan",
    options=days_options,
    index=0,
    help="Select how many days of data to analyze"
)

# Convert "All" to None for the API function
days = None if days_selection == "All" else days_selection

# Run analysis button
if st.sidebar.button("Run Analysis"):
    if jackpot_id:
        analyze_jackpot(jackpot_id, days)
    else:
        st.error("Please enter a valid Jackpot ID")

# Load previous analyses (if any)
st.sidebar.subheader("Recent Analyses")

# This would be populated from a database or cache in a real implementation
recent_jackpots = [
    "feed-skillonnet.redtiger.cash_skillOnNet-Mega Jackpot_38002",
    "feed-skillonnet.redtiger.cash_skillOnNet-Daily Drop_46712",
    "feed-operator.provider.jackpot_example_12345"
]

for recent in recent_jackpots:
    if st.sidebar.button(f"Load {recent[:20]}...", key=recent):
        analyze_jackpot(recent, days)

# Footer with information
st.markdown("---")
st.markdown("Jackpot analysis is based on real-time API data. Last update: " + 
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
