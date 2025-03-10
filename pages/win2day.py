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
from io import BytesIO

# Set page config
st.set_page_config(
    page_title="Original Analysis",
    page_icon="📈",
    layout="wide"
)

# Title and description
st.title("Original Win2Day Analysis")
st.markdown("This is the original analysis script implemented as a Streamlit page.")

# Set the plotting style
style.use('ggplot')

# Function to load data from Google Sheets
@st.cache_data(ttl=3600)
def load_sheet_data():
    """Load data from Google Sheets using gspread and Streamlit secrets"""
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
        
        return df
    
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.info("Make sure you have configured your Streamlit secrets with Google API credentials.")
        return None

def analyze_win2day_data(df, game_to_analyze):
    """
    Analyzes jackpot data for a specific game
    """
    if df is None or game_to_analyze is None:
        return
        
    # Set date as index for analysis
    df = df.set_index("Date")
    
    # Filter for selected game
    filtered_df = df[df["Concat"] == game_to_analyze].copy()
    
    if filtered_df.empty:
        st.warning(f"No data available for {game_to_analyze}")
        return
    
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
        
    # Show summary statistics
    st.subheader("Summary Statistics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Jackpot", f"€{filtered_df['Jackpot Win'].sum():,.2f}")
    col2.metric("Average Win", f"€{filtered_df['Jackpot Win'].mean():,.2f}")
    col3.metric("Highest Win", f"€{filtered_df['Jackpot Win'].max():,.2f}")
    col4.metric("Number of Wins", f"{len(filtered_df)}")

# Load the data first
with st.spinner("Loading data from Google Sheets..."):
    df = load_sheet_data()

if df is not None:
    # Show some basic info about the dataset
    st.success(f"Data loaded successfully! Found {df['Concat'].nunique()} unique games.")
    
    # Add sidebar for game selection
    st.sidebar.header("Analysis Settings")
    
    # Let the user select a game to analyze
    game_options = sorted(df['Concat'].unique().tolist())
    default_game = " €€€ Jackpot" if " €€€ Jackpot" in game_options else game_options[0]
    game_to_analyze = st.sidebar.selectbox(
        "Select Game to Analyze", 
        game_options, 
        index=game_options.index(default_game)
    )
    
    # Add an option to filter by date range
    st.sidebar.subheader("Date Filter (Optional)")
    date_filter = st.sidebar.checkbox("Filter by Date Range")
    
    if date_filter:
        date_min = df["Date"].min().date()
        date_max = df["Date"].max().date()
        date_range = st.sidebar.date_input(
            "Select Date Range",
            value=(date_min, date_max),
            min_value=date_min,
            max_value=date_max
        )
        
        # Apply date filter if selected
        if len(date_range) == 2:
            start_date, end_date = date_range
            mask = (df["Date"].dt.date >= start_date) & (df["Date"].dt.date <= end_date)
            df_filtered = df[mask]
            st.sidebar.info(f"Filtered to {len(df_filtered)} records between {start_date} and {end_date}")
        else:
            df_filtered = df
    else:
        df_filtered = df
    
    # Run analysis button
    run_analysis = st.sidebar.button("Run Analysis", type="primary")
    
    # Show preview of selected data
    with st.expander("Preview Selected Game Data"):
        preview_df = df_filtered[df_filtered["Concat"] == game_to_analyze].head(10)
        st.dataframe(preview_df)
    
    if run_analysis:
        with st.spinner(f"Analyzing {game_to_analyze}..."):
            analyze_win2day_data(df_filtered, game_to_analyze)
    else:
        st.info("Select a game from the sidebar and click 'Run Analysis' to generate the plots.")

# Add explanation
with st.expander("About This Analysis"):
    st.markdown("""
    This page runs the original Win2Day analysis script, adapted to work within Streamlit.
    
    Key features:
    - Select which jackpot game to analyze from the sidebar
    - Optional date filtering to focus on specific time periods
    - Interactive plots showing win distributions and trends
    - Downloads available for both plots and data
    
    The analysis shows:
    - Distribution of jackpot win amounts
    - Scatter plot of individual jackpot wins over time
    - Cumulative jackpot winnings over time
    - Probability plot to assess normality of win distributions
    """)
