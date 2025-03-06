import streamlit as st
import requests
import json
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import style
from matplotlib.ticker import ScalarFormatter
from datetime import datetime, timedelta
from typing import Optional, Union, Dict
import logging
from urllib3.exceptions import InsecureRequestWarning
import warnings
import numpy as np
import seaborn as sns
from scipy import stats
import io
import os

from utils.auth import check_password, logout, initialize_session_state
from utils.ip_manager import log_ip_activity

# Suppress insecure HTTPS warnings
warnings.filterwarnings('ignore', category=InsecureRequestWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set page configuration
st.set_page_config(
    page_title="Jackpot Analysis",
    page_icon="📊",
    layout="wide"
)

# Initialize session state variables
initialize_session_state()

# Function to generate realistic mock data for testing
def generate_mock_data(days=100, seed=None):
    """Generate realistic jackpot data for testing."""
    if seed is not None:
        np.random.seed(seed)
        
    # Create date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    dates = pd.date_range(start=start_date, end=end_date, periods=days)
    
    # Create base amount with growth trend
    base_amount = 5000
    growth_rate = 0.02  # 2% average daily growth
    trend = np.cumprod(np.random.normal(1 + growth_rate, 0.01, days))
    
    # Add some volatility
    volatility = np.random.normal(0, 300, days)
    
    # Calculate amounts
    amounts = base_amount * trend + volatility
    
    # Add periodic drops (jackpot wins)
    num_drops = days // 14  # Approximately one drop every two weeks
    drop_indices = np.random.choice(range(days), size=num_drops, replace=False)
    
    for idx in drop_indices:
        if idx > 0:  # Skip the first day
            drop_percentage = np.random.uniform(0.3, 0.7)  # 30-70% drop
            amounts[idx] = amounts[idx-1] * (1 - drop_percentage)
    
    # Create DataFrame
    df = pd.DataFrame({
        'ts': dates,
        'amount': amounts
    })
    
    return df

class JackpotAPI:
    def __init__(self, base_url: str = "https://grnst-data-store-serv.com"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.verify = False
        # Set shorter timeout to avoid long waits
        self.timeout = 5

    def test_connection(self) -> bool:
        try:
            # Try different endpoints for health check
            endpoints = [
                "/api/health",
                "/health",
                "/api/status",
                "/api/v1/health",
                "/"  # Fallback to root path
            ]
            
            for endpoint in endpoints:
                try:
                    url = f"{self.base_url}{endpoint}"
                    st.info(f"Testing connection to {url}")
                    response = self.session.get(url, timeout=self.timeout)
                    
                    if response.status_code < 400:  # Accept any 2xx or 3xx status code
                        st.success(f"API connection successful (endpoint: {endpoint})")
                        logger.info(f"API connection successful (endpoint: {endpoint})")
                        return True
                except Exception as e:
                    logger.warning(f"Failed to connect to {endpoint}: {str(e)}")
                    continue
            
            st.error("Failed to connect to any API endpoint")
            return False
            
        except Exception as e:
            st.error(f"API connection test failed: {str(e)}")
            logger.error(f"API connection test failed: {str(e)}")
            return False

    def get_timeseries(
        self,
        jackpot_id: str,
        days: Optional[int] = None,
        return_df: bool = True,
        use_mock_data: bool = False
    ) -> Union[Dict, pd.DataFrame]:
        """
        Fetch jackpot timeseries data.

        Args:
            jackpot_id: Identifier for the jackpot
            days: Number of days of data to fetch (optional)
            return_df: If True, returns pandas DataFrame, else raw JSON
            use_mock_data: If True, generates mock data instead of API call
        """
        if use_mock_data:
            st.info("Using generated mock data instead of API")
            mock_data = generate_mock_data(days=days or 100, seed=hash(jackpot_id) % 1000)
            return mock_data
            
        endpoint = f"{self.base_url}/api/timeseries"

        # First try without timespan
        payload = {"jackpot_id": jackpot_id}
        st.info("Trying request without timespan first...")

        try:
            with st.spinner(f"Making request to {endpoint}"):
                response = self.session.post(endpoint, json=payload, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                # If we got no data and days parameter was provided, try with timespan
                if len(data.get("timeseriesData", [])) == 0 and days is not None:
                    st.info(f"No data received, trying with {days} days timespan...")
                    timespan_ms = days * 24 * 60 * 60 * 1000
                    payload["timespan"] = timespan_ms

                    response = self.session.post(endpoint, json=payload, timeout=self.timeout)
                    response.raise_for_status()
                    data = response.json()

            if return_df:
                # Check if timeseriesData exists
                if "timeseriesData" not in data or not data["timeseriesData"]:
                    st.warning("No timeseries data found in API response")
                    return pd.DataFrame()
                    
                df = pd.DataFrame(data["timeseriesData"])
                if not df.empty:
                    # Ensure columns exist
                    if 'ts' not in df.columns or 'amount' not in df.columns:
                        st.error("Expected columns 'ts' and 'amount' not found in response")
                        return pd.DataFrame()
                    
                    # Ensure amount is numeric
                    df['amount'] = pd.to_numeric(df['amount'])
                    df['ts'] = pd.to_datetime(df['ts'], unit='ms')
                    
                    # Show data info in expander
                    with st.expander("View Data Details"):
                        st.write("DataFrame Info")
                        buffer = io.StringIO()
                        df.info(buf=buffer)
                        st.text(buffer.getvalue())
                        
                        st.write("First few rows")
                        st.dataframe(df.head())
                return df
            return data

        except requests.exceptions.RequestException as e:
            st.error(f"Failed to fetch timeseries data: {str(e)}")
            logger.error(f"Failed to fetch timeseries data: {str(e)}")
            return pd.DataFrame()
        except (KeyError, ValueError) as e:
            st.error(f"Failed to process timeseries data: {str(e)}")
            logger.error(f"Failed to process timeseries data: {str(e)}")
            return pd.DataFrame()

def analyze_jackpot(jackpot_id: str, days: Optional[int] = None) -> None:
    """
    Analyze and plot jackpot data in Streamlit.

    Args:
        jackpot_id: Identifier for the jackpot
        days: Optional number of days of data to analyze
    """
    if not jackpot_id:
        st.warning("Please enter a jackpot ID")
        return
    
    api = JackpotAPI()

    if not api.test_connection():
        st.error("Failed to connect to API")
        return

    try:
        # Create a flag for using mock data
        use_mock_data = False
        
        with st.spinner("Fetching jackpot data..."):
            ts_data = api.get_timeseries(
                jackpot_id=jackpot_id,
                days=days,
                return_df=True
            )
            
            # Check if data is empty and offer mock data option
            if ts_data.empty:
                st.warning("No data returned from API")
                if st.checkbox("Generate mock data for testing?"):
                    st.info("Creating mock data for visualization testing")
                    # Create mock time series data
                    dates = pd.date_range(start='2020-01-01', periods=100, freq='D')
                    amounts = np.linspace(1000, 10000, 100) + np.random.normal(0, 500, 100)
                    # Create sharp drops every ~14 days
                    for i in range(7, 100, 14):
                        amounts[i] = amounts[i-1] * 0.7  # 30% drop
                    
                    ts_data = pd.DataFrame({
                        'ts': dates,
                        'amount': amounts
                    })
                    use_mock_data = True
        
        if not ts_data.empty:
            if use_mock_data:
                st.success("Using mock data for visualization testing")
            else:
                st.success(f"Successfully retrieved data for {jackpot_id}")
            st.success(f"Successfully retrieved data for {jackpot_id}")
            
            # Filter for specific start date
            ts_data = ts_data[ts_data['ts'] >= datetime(2020, 1, 1)]
            if ts_data.empty:
                st.warning("No data available after January 1, 2020")
                return
                
            # Find significant drops in the data
            ts_data['diff'] = ts_data['amount'].diff()
            ts_data['diff_pct'] = ts_data['amount'].pct_change()
            ts_data['significant_drop'] = ts_data['diff_pct'] < -0.1
            previous_values = ts_data['amount'].shift(1)
            ts_data['previous_amount'] = previous_values

            # Filter for significant drops
            significant_drops = ts_data[ts_data['significant_drop']]
            significant_drops['previous_amount'] = previous_values[ts_data['significant_drop']]

            if significant_drops.empty:
                st.warning("No significant drops found in the data")
                return
                
            # Calculate statistics
            average_drop = significant_drops['previous_amount'].mean()
            days_span = (ts_data['ts'].iloc[-1] - ts_data['ts'].iloc[0]).days
            start_value = ts_data['amount'].iloc[0]
            end_value = ts_data['amount'].iloc[-1]
            growth = (end_value - start_value) / days_span if days_span > 0 else 0
            
            # Display stats in columns
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Average Drop Amount", f"{average_drop:.2f}")
            with col2:
                st.metric("Data Time Span", f"{days_span} days")
            with col3:
                st.metric("Daily Growth Rate", f"{growth:.2f}")
            
            # Create and display plots
            st.subheader("Jackpot Amount Over Time")
            
            # Use Streamlit's native plotting capabilities first
            st.line_chart(ts_data.set_index('ts')['amount'])
            
            st.write("Detailed Plot with Drop Analysis")
            
            try:
                # Clear any previous matplotlib plots
                plt.close('all')
                
                # Create a new figure with explicit figsize
                fig1, ax1 = plt.subplots(figsize=(10, 6))
                
                # Basic plotting
                ax1.plot(ts_data['ts'], ts_data['amount'], linewidth=1.5)
                
                # Add scatter points for drops
                if not significant_drops.empty:
                    ax1.scatter(significant_drops['ts'], significant_drops['amount'], color='red', label='Significant Drop')
                
                # Add reference line
                ax1.axhline(y=average_drop, color='r', linestyle='--', label='Average Drop')
                
                # Set labels and formatting
                ax1.set_title(f"{jackpot_id} Jackpot Over Time")
                ax1.set_xlabel("Time")
                ax1.set_ylabel("Amount")
                ax1.yaxis.set_major_formatter(ScalarFormatter())
                plt.xticks(rotation=45)
                plt.tight_layout()
                ax1.legend()
                
                # Add debug information
                st.write(f"Figure size: {fig1.get_size_inches()}")
                st.write(f"Data points: {len(ts_data)}, Drops: {len(significant_drops)}")
                
                # Display the plot
                st.pyplot(fig1)
            except Exception as plot_error:
                st.error(f"Error creating time series plot: {plot_error}")
                
                # Fallback to a simpler plot
                st.write("Fallback plot:")
                simple_fig, simple_ax = plt.subplots()
                simple_ax.plot(ts_data['ts'], ts_data['amount'])
                simple_ax.set_title("Jackpot Over Time (Simple View)")
                st.pyplot(simple_fig)
            
            # Histogram of significant drops
            st.subheader("Distribution of Significant Drops")
            fig2, ax2 = plt.subplots(figsize=(10, 6))
            sns.histplot(significant_drops['previous_amount'], kde=True, ax=ax2, color='#8E44AD', bins=30)
            ax2.set_ylabel('Frequency')
            ax2.set_xlabel('Amount')
            ax2.set_title('Significant Drops')
            ax2.xaxis.set_major_locator(plt.MaxNLocator(25))
            ax2.xaxis.set_major_formatter(ScalarFormatter())
            plt.tight_layout()
            st.pyplot(fig2)
            
            # Probability plot
            st.subheader("Probability Distribution Analysis")
            fig3, ax3 = plt.subplots(figsize=(10, 6))
            stats.probplot(significant_drops['previous_amount'], plot=ax3, fit=True)
            ax3.set_title('Significant Drops Probability Plot')
            plt.tight_layout()
            st.pyplot(fig3)
            
            # Cumulative sum plot
            st.subheader("Cumulative Sum of Drops")
            fig4, ax4 = plt.subplots(figsize=(10, 6))
            
            # Calculate cumulative daily wins
            cumulative_daily_wins = significant_drops['previous_amount'].cumsum()
            cumulative_daily_wins.index = significant_drops['ts']
            
            ax4.bar(cumulative_daily_wins.index, cumulative_daily_wins.values,
                   edgecolor='black', color='g')
            # Thicken the bars
            [i.set_linewidth(2) for i in ax4.patches]
            
            ax4.set_title('Drops Cumsum')
            ax4.set_xlabel('Date')
            ax4.set_ylabel('Amount')
            ax4.tick_params(axis='x', rotation=45)
            ax4.xaxis.set_major_locator(plt.MaxNLocator(10))
            ax4.yaxis.set_major_formatter(ScalarFormatter())
            ax4.ticklabel_format(axis='y', style='plain')
            plt.tight_layout()
            st.pyplot(fig4)
            
            # Download options
            st.subheader("Download Options")
            download_col1, download_col2 = st.columns(2)
            
            with download_col1:
                # Download the data
                csv = ts_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Raw Data as CSV",
                    data=csv,
                    file_name=f"{jackpot_id}_data.csv",
                    mime="text/csv"
                )
                
            with download_col2:
                # Download the analysis results
                significant_csv = significant_drops.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Analysis Results as CSV",
                    data=significant_csv,
                    file_name=f"{jackpot_id}_analysis.csv",
                    mime="text/csv"
                )
                
        else:
            period = f" over the last {days} days" if days else ""
            st.error(f"No data received for jackpot {jackpot_id}{period}")

    except Exception as e:
        st.error(f"Analysis failed: {str(e)}")
        logger.error(f"Analysis failed: {str(e)}")

# Main app code
def main():
    # Check if the user is authenticated
    if check_password():
        # Log the page view with IP
        if "username" in st.session_state and "ip_address" in st.session_state:
            log_ip_activity(st.session_state["username"], "page_view_jackpot_analysis", st.session_state["ip_address"])

        # Display logout button in the sidebar
        st.sidebar.button("Logout", on_click=logout)

        # Display user information
        st.sidebar.info(f"Logged in as: {st.session_state['username']} ({st.session_state['user_role']})")

        # Display IP address (only for admins)
        if st.session_state.get("user_role") == "admin":
            st.sidebar.info(f"Your IP: {st.session_state['ip_address']}")

        # Main app layout
        st.title("📊 Jackpot Analysis")
        st.write("Analyze jackpot data and visualize trends.")
        
        # Add data source selector
        st.sidebar.subheader("Data Source")
        data_source = st.sidebar.radio(
            "Select Data Source",
            ["API (Real Data)", "Mock Data (Demo)"],
            index=1,  # Default to mock data since API is not working
            help="Choose to use real API data or generated mock data"
        )
        use_mock_data = (data_source == "Mock Data (Demo)")
        
        if use_mock_data:
            st.info("🧪 Using simulated mock data for demonstration purposes")
        else:
            # Advanced options for API
            st.sidebar.subheader("API Settings")
            api_url = st.sidebar.text_input(
                "API URL", 
                value="https://grnst-data-store-serv.com",
                help="The base URL of the jackpot API"
            )
        
        # Debugging options for admin users
        if st.session_state.get("user_role") == "admin":
            st.sidebar.subheader("Admin Options")
            debug = st.sidebar.checkbox("Enable Debug Mode", value=False)
            
            if debug:
                st.sidebar.info("Debug mode enabled")
                matplotlib_backend = plt.get_backend()
                st.sidebar.write(f"Matplotlib backend: {matplotlib_backend}")
                
                if st.sidebar.button("Use Agg Backend"):
                    plt.switch_backend('Agg')
                    st.sidebar.success(f"Switched to Agg backend")
                    st.experimental_rerun()
        
        # Input form
        with st.form("jackpot_analysis_form"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                if use_mock_data:
                    jackpot_id = st.text_input(
                        "Mock Jackpot Name", 
                        value="Demo_Jackpot_1",
                        help="Enter a name for the mock jackpot (used as random seed)"
                    )
                else:
                    jackpot_id = st.text_input(
                        "Jackpot ID", 
                        value="feeds-jackpots.s3.amazonaws.com_Ave Caesar_LEAVECAESAR",
                        help="Enter the jackpot identifier"
                    )
                
            with col2:
                days = st.number_input(
                    "Days of Data", 
                    min_value=7, 
                    max_value=365,
                    value=90,
                    help="Number of days of data to analyze"
                )
                
            submit_button = st.form_submit_button("Analyze Jackpot")
            
        if submit_button:
            try:
                # Store the analysis parameters
                st.session_state["last_jackpot_id"] = jackpot_id
                st.session_state["last_days"] = days
                st.session_state["last_used_mock"] = use_mock_data
                
                analyze_jackpot(jackpot_id, days, use_mock_data)
            except Exception as e:
                st.error(f"Analysis failed: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
            
        # Display previous analysis if available
        if "last_jackpot_id" in st.session_state and "last_days" in st.session_state:
            with st.expander("Previous Analysis", expanded=False):
                mock_text = "(Mock Data)" if st.session_state.get("last_used_mock", False) else "(API Data)"
                st.info(f"Last analyzed: {st.session_state['last_jackpot_id']} - {st.session_state['last_days']} days {mock_text}")
                
                if st.button("Rerun Previous Analysis"):
                    use_mock = st.session_state.get("last_used_mock", use_mock_data)
                    analyze_jackpot(st.session_state["last_jackpot_id"], st.session_state["last_days"], use_mock)
        
        # Additional help section
        with st.expander("Help & Info"):
            st.markdown("""
            ### About the Jackpot Analysis Page
            
            This page helps you analyze jackpot data and visualize important trends:
            
            - **Mock Data Option**: If the API is unavailable, you can still test functionality with realistic mock data
            - **Time Series Analysis**: See jackpot amounts over time with highlighted drops
            - **Drop Statistics**: Analyze when and how much jackpots drop
            
            ### How to use:
            1. Select data source (API or Mock Data)
            2. Enter jackpot ID (or mock name)
            3. Select the number of days to analyze
            4. Click "Analyze Jackpot"
            
            You can download the analysis results as CSV files for further processing.
            """)
            
    else:
        st.warning("Please log in to access the jackpot analysis features.")

if __name__ == "__main__":
    main()
