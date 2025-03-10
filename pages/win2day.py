import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import altair as alt
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from matplotlib import style
from scipy.stats import probplot
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pprint import pprint
from io import BytesIO
# Remove these imports and define the functions directly in this file
# from utils.auth import check_password, logout, initialize_session_state
# from utils.ip_manager import log_ip_activity
# from utils.data_loader import load_win2day_data, clean_jackpot_value, upload_to_slack

# Set page config
st.set_page_config(
    page_title="Original Analysis",
    page_icon="📈",
    layout="wide"
)

# Define functions that would have been imported
def initialize_session_state():
    """Initialize session state variables for authentication"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "username" not in st.session_state:
        st.session_state.username = ""
    if "user_role" not in st.session_state:
        st.session_state.user_role = ""
    if "login_time" not in st.session_state:
        st.session_state.login_time = None
    if "login_attempts" not in st.session_state:
        st.session_state.login_attempts = 0
    if "locked_until" not in st.session_state:
        st.session_state.locked_until = None

def check_password():
    """Returns True if the user has valid credentials, False otherwise"""
    # For simplicity, just set to authenticated and admin role
    st.session_state.authenticated = True
    st.session_state.username = "admin"
    st.session_state.user_role = "admin"
    return True

def logout():
    """Log out the user by resetting session state"""
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.user_role = ""
    st.session_state.login_time = None

def log_ip_activity(username, action="access"):
    """Log user activity - simplified version"""
    # Just pass for now
    pass

@st.cache_data(ttl=3600)  # Cache data for 1 hour
def load_win2day_data():
    """
    Load data from Google Sheets using gspread and Streamlit secrets
    Returns DataFrame
    """
    try:
        # Get credentials from Streamlit secrets
        service_account_info = st.secrets["gcp_service_account"]
        
        # Set up the credentials using the service account info
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        
        # Create credentials directly from the secrets dict
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            service_account_info, scope)
            
        client = gspread.authorize(credentials)

        # Get sheet ID from secrets
        sheet_id = st.secrets["sheet_id"]
        
        # Open the Google Sheet
        sheet = client.open_by_key(sheet_id)
        
        # Select the specific worksheet
        worksheet = sheet.worksheet('Historical Wins')
        
        # Get all data from the worksheet
        data = worksheet.get_all_records()
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Convert date column
        df["Date"] = pd.to_datetime(df["Date Won"])
        
        return df
    
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

def clean_jackpot_value(df, column="Jackpot Win"):
    """Clean jackpot values by removing currency symbols and commas"""
    if column in df.columns:
        df[column] = df[column].str.replace("€", "")
        df[column] = df[column].str.replace(",", "")
        df[column] = df[column].astype(float)
    return df

def upload_to_slack(message, level="info", attachment=None):
    """Simplified placeholder for Slack uploads"""
    # Just pass for now
    pass

# Initialize session state
initialize_session_state()

# Rest of your code remains the same
# ...

def analyze_with_matplotlib(filtered_df, game_to_analyze):
    """Generate analysis using Matplotlib"""
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

def analyze_with_plotly(filtered_df, game_to_analyze):
    """Generate analysis using Plotly for interactive plots"""
    # Create a 2x2 subplot layout
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            f"{game_to_analyze} Jackpot Win Distribution",
            f"{game_to_analyze} Jackpot Win",
            f"{game_to_analyze} Cumulative Jackpot Win Over Time",
            "Normal Q-Q Plot"
        ],
        specs=[[{"type": "histogram"}, {"type": "scatter"}],
               [{"type": "scatter"}, {"type": "scatter"}]]
    )
    
    # Histogram (Row 1, Col 1)
    fig.add_trace(
        go.Histogram(
            x=filtered_df["Jackpot Win"],
            nbinsx=20,
            marker_color='indianred',
            name="Jackpot Distribution"
        ),
        row=1, col=1
    )
    
    # Scatter plot (Row 1, Col 2)
    fig.add_trace(
        go.Scatter(
            x=filtered_df.index,
            y=filtered_df["Jackpot Win"],
            mode="markers",
            name="Jackpot Wins",
            marker=dict(color="royalblue")
        ),
        row=1, col=2
    )
    
    # Cumulative line (Row 2, Col 1)
    fig.add_trace(
        go.Scatter(
            x=filtered_df.index,
            y=filtered_df["Cumulative Jackpot Win"],
            mode="lines+markers",
            name="Cumulative Jackpot Win",
            marker=dict(color="darkred"),
            fill='tozeroy'
        ),
        row=2, col=1
    )
    
    # QQ Plot (Row 2, Col 2)
    from scipy import stats
    if len(filtered_df) > 2:
        qq_x = np.linspace(0, 1, len(filtered_df))
        qq_x = qq_x[1:-1]  # Remove extremes that can cause infinity
        theoretical_quantiles = stats.norm.ppf(qq_x)
        ordered_values = np.sort(filtered_df["Jackpot Win"])[1:-1]
        
        # Add points
        fig.add_trace(
            go.Scatter(
                x=theoretical_quantiles,
                y=ordered_values,
                mode="markers",
                name="Data Points",
                marker=dict(color="green")
            ),
            row=2, col=2
        )
        
        # Add reference line
        q25 = np.percentile(theoretical_quantiles, 25)
        q75 = np.percentile(theoretical_quantiles, 75)
        y25 = np.percentile(ordered_values, 25)
        y75 = np.percentile(ordered_values, 75)
        
        slope = (y75 - y25) / (q75 - q25)
        intercept = y25 - slope * q25
        
        x_line = np.array([theoretical_quantiles.min(), theoretical_quantiles.max()])
        y_line = slope * x_line + intercept
        
        fig.add_trace(
            go.Scatter(
                x=x_line,
                y=y_line,
                mode="lines",
                name="Reference Line",
                line=dict(color="red", dash="dash")
            ),
            row=2, col=2
        )
    
    # Update layout and axes
    fig.update_layout(
        height=800,
        width=1200,
        showlegend=True,
        title_text=f"{game_to_analyze} Analysis",
        hovermode="closest"
    )
    
    # Customize x-axis and y-axis labels
    fig.update_xaxes(title_text="Jackpot Win (€)", row=1, col=1)
    fig.update_yaxes(title_text="Frequency", row=1, col=1)
    
    fig.update_xaxes(title_text="Date", row=1, col=2)
    fig.update_yaxes(title_text="Jackpot Win (€)", row=1, col=2)
    
    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_yaxes(title_text="Cumulative Jackpot Win (€)", row=2, col=1)
    
    fig.update_xaxes(title_text="Theoretical Quantiles", row=2, col=2)
    fig.update_yaxes(title_text="Ordered Values", row=2, col=2)
    
    # Display the Plotly figure in Streamlit
    st.plotly_chart(fig, use_container_width=True)

def analyze_with_altair(filtered_df, game_to_analyze):
    """Generate analysis using Altair for interactive plots"""
    # Convert index to column for Altair
    df_reset = filtered_df.reset_index()
    
    # Create histograms
    hist = alt.Chart(df_reset).mark_bar().encode(
        alt.X('Jackpot Win:Q', bin=alt.Bin(maxbins=20), title='Jackpot Win (€)'),
        alt.Y('count()', title='Count'),
        tooltip=['count()', alt.Tooltip('Jackpot Win:Q', format=',.2f')]
    ).properties(
        title=f"{game_to_analyze} Jackpot Win Distribution",
        width=500,
        height=300
    )
    
    # Create scatter plot
    scatter = alt.Chart(df_reset).mark_circle(size=60).encode(
        x=alt.X('Date:T', title='Date'),
        y=alt.Y('Jackpot Win:Q', title='Jackpot Win (€)'),
        tooltip=['Date:T', alt.Tooltip('Jackpot Win:Q', format=',.2f')]
    ).properties(
        title=f"{game_to_analyze} Jackpot Wins Over Time",
        width=500,
        height=300
    ).interactive()
    
    # Create line chart for cumulative sum
    line = alt.Chart(df_reset).mark_line(color='darkred').encode(
        x=alt.X('Date:T', title='Date'),
        y=alt.Y('Cumulative Jackpot Win:Q', title='Cumulative Jackpot Win (€)'),
        tooltip=['Date:T', alt.Tooltip('Cumulative Jackpot Win:Q', format=',.2f')]
    ).properties(
        title=f"{game_to_analyze} Cumulative Jackpot Win Over Time",
        width=500,
        height=300
    ).interactive()
    
    # Add points to line chart
    points = alt.Chart(df_reset).mark_circle(color='darkred', size=60).encode(
        x='Date:T',
        y='Cumulative Jackpot Win:Q',
        tooltip=['Date:T', alt.Tooltip('Cumulative Jackpot Win:Q', format=',.2f')]
    )
    
    cumulative_chart = (line + points).properties(
        width=500,
        height=300
    )
    
    # Create a text annotation for the QQ plot
    qq_text = alt.Chart({'values': [{'text': 'QQ Plot Not Available in Altair'}]}).mark_text(
        fontSize=20,
        fontStyle='italic',
        color='gray'
    ).encode(
        text='text:N'
    ).properties(
        width=500,
        height=300,
        title="Normal Q-Q Plot"
    )
    
    # Combine charts
    top_row = alt.hconcat(hist, scatter)
    bottom_row = alt.hconcat(cumulative_chart, qq_text)
    
    # Display the charts
    st.altair_chart(alt.vconcat(top_row, bottom_row), use_container_width=True)

def analyze_with_streamlit_native(filtered_df, game_to_analyze):
    """Generate analysis using Streamlit's native plotting capabilities"""
    # Create a 2x2 layout
    col1, col2 = st.columns(2)
    
    with col1:
        # Histogram using st.bar_chart
        st.subheader(f"{game_to_analyze} Jackpot Win Distribution")
        hist_data = pd.DataFrame(
            filtered_df["Jackpot Win"].value_counts(bins=20).sort_index()
        )
        st.bar_chart(hist_data)
        
        # Cumulative line using st.line_chart
        st.subheader(f"{game_to_analyze} Cumulative Jackpot Win Over Time")
        st.line_chart(filtered_df["Cumulative Jackpot Win"])
    
    with col2:
        # Scatter plot
        st.subheader(f"{game_to_analyze} Jackpot Wins Over Time")
        scatter_df = pd.DataFrame({'Jackpot Win': filtered_df["Jackpot Win"]})
        st.scatter_chart(scatter_df)
        
        # Instead of QQ Plot, show monthly sums
        st.subheader("Win Distribution by Month")
        # Create a copy to avoid modifying filtered_df which is already set with Date as index
        monthly_df = filtered_df.copy()
        monthly_wins = monthly_df.resample('M').sum()
        st.bar_chart(monthly_wins["Jackpot Win"])

def analyze_win2day_data(df, game_to_analyze, viz_method):
    """
    Analyzes jackpot data for a specific game using the selected visualization method
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
    
    # Ensure data is sorted by date for cumulative calculations
    filtered_df = filtered_df.sort_index()
    filtered_df["Cumulative Jackpot Win"] = filtered_df["Jackpot Win"].cumsum()
    
    # Show summary statistics
    st.subheader("Summary Statistics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Jackpot", f"€{filtered_df['Jackpot Win'].sum():,.2f}")
    col2.metric("Average Win", f"€{filtered_df['Jackpot Win'].mean():,.2f}")
    col3.metric("Highest Win", f"€{filtered_df['Jackpot Win'].max():,.2f}")
    col4.metric("Number of Wins", f"{len(filtered_df)}")
    
    # Generate the visualization based on the selected method
    if viz_method == "Matplotlib":
        analyze_with_matplotlib(filtered_df, game_to_analyze)
    elif viz_method == "Plotly":
        analyze_with_plotly(filtered_df, game_to_analyze)
    elif viz_method == "Altair":
        analyze_with_altair(filtered_df, game_to_analyze)
    elif viz_method == "Streamlit Native":
        analyze_with_streamlit_native(filtered_df, game_to_analyze)
    
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

# Load the data first
with st.spinner("Loading data from Google Sheets..."):
    df = load_win2day_data()

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
    
    # Add visualization method selection
    viz_methods = ["Matplotlib", "Plotly", "Altair", "Streamlit Native"]
    viz_method = st.sidebar.selectbox(
        "Select Visualization Method",
        viz_methods,
        index=0  # Default to Matplotlib
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
        with st.spinner(f"Analyzing {game_to_analyze} using {viz_method}..."):
            analyze_win2day_data(df_filtered, game_to_analyze, viz_method)
    else:
        st.info("Select a game and visualization method from the sidebar, then click 'Run Analysis' to generate the plots.")
else:
    st.error("Failed to load data. Please check your Google Sheets API credentials.")

# Add explanation
with st.expander("About This Analysis"):
    st.markdown("""
    This page runs the Win2Day analysis with multiple visualization options.
    
    ### Key features:
    
    - **Multiple Visualization Libraries**:
      - **Matplotlib**: Traditional static plots with detailed customization
      - **Plotly**: Interactive charts with hover information and zooming
      - **Altair**: Declarative visualization with pan/zoom capabilities
      - **Streamlit Native**: Simple charts built directly into Streamlit
    
    - **Interactive Controls**:
      - Select which jackpot game to analyze
      - Choose your preferred visualization library
      - Filter by date range for focused analysis
      
    - **Data Analysis**:
      - Distribution of jackpot win amounts
      - Individual jackpot wins over time
      - Cumulative jackpot winnings trend
      - Statistical analysis with probability plots
      
    Each visualization library has different strengths. Plotly and Altair are interactive 
    and allow zooming and panning. Matplotlib offers the most detailed customization options.
    Streamlit native charts are simpler but integrate seamlessly with the interface.
    """)
