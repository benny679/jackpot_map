import streamlit as st
import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import altair as alt
from datetime import datetime, timedelta
import io
import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
# Add this block near the beginning of your main file, after imports and before any functions

# Set environment variables from secrets for the entire application
import os
if 'slack' in st.secrets:
    # Make Slack credentials available as environment variables
    os.environ['SLACK_TOKEN'] = st.secrets.slack.slack_token
    os.environ['SLACK_CHANNEL_ID'] = st.secrets.slack.channel_id

from utils.auth import check_password, logout, initialize_session_state
from utils.ip_manager import log_ip_activity
from utils.data_loader import upload_to_slack

# Set page configuration
st.set_page_config(
    page_title="KPI Dashboard - Jackpot Map",
    page_icon="📊",
    layout="wide"
)

# Initialize session state variables
initialize_session_state()

# Formatting functions for charts (kept for the static chart exports)
def format_currency(x, pos):
    """Format numbers as currency."""
    return f'£{x:,.0f}' if x >= 0 else f'-£{abs(x):,.0f}'

def format_number(x, pos):
    """Format numbers with thousand separators."""
    return f'{x:,.0f}'

# Function to load KPI data from Google Sheet
@st.cache_data(ttl=3600)  # Cache data for 1 hour
def load_kpi_data():
    """Load KPI data from Google Sheets."""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        client = gspread.authorize(creds)
        
        # Open the specific sheet
        sheet = client.open("Low Vol JPS").worksheet("KPIs")
        data = sheet.get_all_values()

        # Convert to DataFrame
        df = pd.DataFrame(data[2:], columns=data[1])  # Using row 1 as headers, data starts from row 2

        # Clean up column names
        df.columns = df.columns.str.strip()

        # Convert numeric columns
        numeric_columns = [
            'New Games Added', 'Scrapers added to backlog', 'N New Games Played', 'Scrapers Done',
            'Scrapers in backlog', 'Av. days to model', 'Jackpots Played',
            'Jackpots Won', 'Jackpots Missed', 'Reports Sent', 'KPIs recorded',
            'Meetings Run', 'Total', 'Paused', 'Added this week'
        ]

        for col in numeric_columns:
            if col in df.columns:  # Check if column exists
                df[col] = pd.to_numeric(df[col].replace(['', '-'], np.nan), errors='coerce')

        # Convert EV Added to numeric, removing £ and , characters
        if 'EV Added' in df.columns:
            df['EV Added'] = df['EV Added'].replace('', np.nan)
            df['EV Added'] = df['EV Added'].astype(str)
            # Remove currency symbols, commas and any other non-numeric characters except decimal point
            df['EV Added'] = df['EV Added'].str.replace('£', '')
            df['EV Added'] = df['EV Added'].str.replace(',', '')
            df['EV Added'] = df['EV Added'].str.replace(' ', '')
            # Convert to numeric, coercing errors to NaN
            df['EV Added'] = pd.to_numeric(df['EV Added'], errors='coerce')
            # Replace NaN with 0 for charting purposes
            df['EV Added'] = df['EV Added'].fillna(0)

        # Convert Week Commencing to datetime
        if 'Week Commencing' in df.columns:
            df['Week Commencing'] = pd.to_datetime(df['Week Commencing'], format='%d/%m/%Y', errors='coerce')

        return df
    except Exception as e:
        st.error(f"Error loading KPI data: {str(e)}")
        return pd.DataFrame()

# Function to create a static stacked area chart for exporting to Slack
def create_static_stacked_area_chart(df, columns, start_date=None, end_date=None, date_format='%d/%m/%Y', date_interval='weekly', y_limit=None):
    """Create a static stacked area chart for exporting."""
    plt.style.use('ggplot')
    
    # Specify colors for the chart
    colors = ['#ffd700', '#0084ff', '#04ff00', '#ff3c00', '#ff0084', '#9932CC', '#00CED1', '#FFA07A']
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Filter to columns that exist in the dataframe
    existing_columns = [col for col in columns if col in df.columns]
    
    if not existing_columns:
        return None
    
    # Filter out rows with missing Week Commencing
    df = df[df['Week Commencing'].notna()].copy()
    
    # Sort by date to ensure proper chronological order
    df = df.sort_values('Week Commencing')
    
    # Create a copy of the data for plotting
    plot_data = df.set_index('Week Commencing')[existing_columns].copy()
    
    # Fill NaN values with 0 for proper stacking
    plot_data = plot_data.fillna(0)
    
    # Process date range parameters
    if start_date is None:
        # Default to first date in data
        start_date = plot_data.index.min()
    
    if end_date is None:
        # Default to last date in data
        end_date = plot_data.index.max()
    
    # Create stacked area chart based on the columns
    ax.stackplot(
        plot_data.index,
        plot_data.values.T,
        labels=plot_data.columns,
        colors=colors[:len(existing_columns)],
        alpha=0.8,
        edgecolor='black',
    )
    
    # Set x-axis limits based on parameters
    ax.set_xlim(start_date, end_date)
    
    # Configure x-axis date ticks based on interval
    if date_interval == 'daily':
        ax.xaxis.set_major_locator(mdates.DayLocator())
    elif date_interval == 'weekly':
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))  # Monday
    elif date_interval == 'monthly':
        ax.xaxis.set_major_locator(mdates.MonthLocator())
    
    # Format the plot
    ax.set_title('KPI Metrics Over Time', fontsize=14, pad=20)
    ax.set_xlabel('Week Commencing', fontsize=12)
    ax.set_ylabel('Value', fontsize=12)
    ax.tick_params(axis='x', rotation=45, labelsize=10)
    ax.tick_params(axis='y', labelsize=10)
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Format x-axis with dates using the specified format
    ax.xaxis.set_major_formatter(mdates.DateFormatter(date_format))
    
    # Format y-axis with proper number formatting
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(format_number))
    
    # Ensure y-axis starts at 0
    if y_limit:
        ax.set_ylim(0, y_limit)
    else:
        ax.set_ylim(0, None)
    
    # Add legend with good placement
    ax.legend(
        loc='upper left',
        fontsize=10,
        framealpha=0.9,
        facecolor='white',
        edgecolor='gray'
    )
    
    plt.tight_layout(pad=3.0)
    return fig

# Function to create a static EV Added chart for exporting to Slack
def create_static_ev_added_chart(df, start_date=None, end_date=None, date_format='%d/%m/%Y', date_interval='weekly'):
    """Create a static EV Added chart for exporting."""
    plt.style.use('ggplot')
    
    # Use gold color for money/value
    colors = ['#DAA520']  # Golden color
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Make sure EV Added column exists
    if 'EV Added' not in df.columns:
        return None
    
    # Filter out rows with missing Week Commencing
    df = df[df['Week Commencing'].notna()].copy()
    
    # Sort by date to ensure proper chronological order
    df = df.sort_values('Week Commencing')
    
    # Create a copy of the data for plotting
    ev_data = df[['Week Commencing', 'EV Added']].copy()
    
    # Replace NaN with 0
    ev_data = ev_data.fillna(0)
    
    # Set the index to Week Commencing for plotting
    ev_data = ev_data.set_index('Week Commencing')
    
    # Process date range parameters
    if start_date is None:
        # Default to first date in data
        start_date = ev_data.index.min()
    
    if end_date is None:
        # Default to last date in data
        end_date = ev_data.index.max()
    
    # Plot line for EV Added
    ax.plot(
        ev_data.index,
        ev_data['EV Added'],
        label='EV Added',
        color="#000000",
        marker='o',
        markersize=5,
        alpha=0.8
    )
    
    # Create the area chart
    ax.fill_between(
        ev_data.index,
        ev_data['EV Added'],
        0,  # Fill down to 0
        color=colors[0],
        alpha=0.8,
        label='EV Added'
    )
    
    # Set x-axis limits based on parameters
    ax.set_xlim(start_date, end_date)
    
    # Configure x-axis date ticks based on interval
    if date_interval == 'daily':
        ax.xaxis.set_major_locator(mdates.DayLocator())
    elif date_interval == 'weekly':
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))  # Monday
    elif date_interval == 'monthly':
        ax.xaxis.set_major_locator(mdates.MonthLocator())
    
    # Format the plot
    ax.set_title('EV Added Over Time', fontsize=14, pad=20)
    ax.set_xlabel('Week Commencing', fontsize=12)
    ax.set_ylabel('EV Added (£)', fontsize=12)
    ax.tick_params(axis='x', rotation=45, labelsize=10)
    ax.tick_params(axis='y', labelsize=10)
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Format x-axis with dates using the specified format
    ax.xaxis.set_major_formatter(mdates.DateFormatter(date_format))
    
    # Format y-axis with currency formatting
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(format_currency))
    
    # Ensure y-axis starts at 0
    ax.set_ylim(0, None)
    
    plt.tight_layout(pad=3.0)
    return fig

# Function to create an interactive stacked area chart with Altair
def create_interactive_stacked_area_chart(df, columns, start_date=None, end_date=None, y_limit=None):
    """Create an interactive stacked area chart with Altair."""
    # Filter to columns that exist in the dataframe
    existing_columns = [col for col in columns if col in df.columns]
    
    if not existing_columns:
        st.error("None of the requested columns exist in the data")
        return None
    
    # Filter out rows with missing Week Commencing
    df = df[df['Week Commencing'].notna()].copy()
    
    # Sort by date to ensure proper chronological order
    df = df.sort_values('Week Commencing')
    
    # Process date range parameters
    if start_date is None:
        # Default to first date in data
        start_date = df['Week Commencing'].min()
    
    if end_date is None:
        # Default to last date in data
        end_date = df['Week Commencing'].max()
    
    # Filter by date range
    df = df[(df['Week Commencing'] >= start_date) & (df['Week Commencing'] <= end_date)]
    
    # Prepare data for Altair
    # We need to reshape the data from wide to long format
    plot_data = df[['Week Commencing'] + existing_columns].copy()
    plot_data = plot_data.melt(
        id_vars=['Week Commencing'],
        value_vars=existing_columns,
        var_name='KPI',
        value_name='Value'
    )
    
    # Fill NaN values with 0
    plot_data['Value'] = plot_data['Value'].fillna(0)
    
    # Create a selection for the legend
    selection = alt.selection_point(fields=['KPI'], bind='legend')
    
    # Create Altair chart
    chart = alt.Chart(plot_data).mark_area().encode(
        x=alt.X('Week Commencing:T', title='Week Commencing'),
        y=alt.Y('sum(Value):Q', title='Value', scale=alt.Scale(domain=[0, y_limit]) if y_limit else alt.Scale(zero=True)),
        color=alt.Color('KPI:N', scale=alt.Scale(scheme='category10')),
        tooltip=[
            alt.Tooltip('Week Commencing:T', title='Date', format='%d %b %Y'),
            alt.Tooltip('KPI:N', title='Metric'),
            alt.Tooltip('Value:Q', title='Value', format=',.0f')
        ],
        opacity=alt.condition(selection, alt.value(0.8), alt.value(0.2))
    ).add_params(
        selection
    ).properties(
        title='KPI Metrics Over Time',
        height=400
    ).configure_axis(
        labelFontSize=12,
        titleFontSize=14
    ).configure_title(
        fontSize=16
    ).configure_legend(
        titleFontSize=14,
        labelFontSize=12
    ).interactive()
    
    return chart

# Function to create an interactive EV Added chart with Altair
def create_interactive_ev_added_chart(df, start_date=None, end_date=None):
    """Create an interactive EV Added chart with Altair."""
    # Make sure EV Added column exists
    if 'EV Added' not in df.columns:
        st.error("'EV Added' column doesn't exist in the data")
        return None
    
    # Filter out rows with missing Week Commencing
    df = df[df['Week Commencing'].notna()].copy()
    
    # Sort by date to ensure proper chronological order
    df = df.sort_values('Week Commencing')
    
    # Process date range parameters
    if start_date is None:
        # Default to first date in data
        start_date = df['Week Commencing'].min()
    
    if end_date is None:
        # Default to last date in data
        end_date = df['Week Commencing'].max()
    
    # Filter by date range
    filtered_df = df[(df['Week Commencing'] >= start_date) & (df['Week Commencing'] <= end_date)].copy()
    
    # Check if we have any data to plot
    if filtered_df.empty or filtered_df['EV Added'].sum() == 0:
        st.warning("No EV Added data to display for the selected date range.")
        return None
    
    # Prepare data for Altair
    plot_data = filtered_df[['Week Commencing', 'EV Added']].copy()
    
    # Explicitly make sure values are numeric and replace NaN with 0
    plot_data['EV Added'] = pd.to_numeric(plot_data['EV Added'], errors='coerce').fillna(0)
    
    # Create a base chart
    base = alt.Chart(plot_data).encode(
        x=alt.X('Week Commencing:T', title='Week Commencing', 
                axis=alt.Axis(format='%d %b %y', labelAngle=-45))
    )
    
    # Create area chart
    area = base.mark_area(
        color='goldenrod',
        opacity=0.6
    ).encode(
        y=alt.Y('EV Added:Q', title='EV Added (£)', scale=alt.Scale(zero=True)),
        tooltip=[
            alt.Tooltip('Week Commencing:T', title='Date', format='%d %b %Y'),
            alt.Tooltip('EV Added:Q', title='EV Added', format='£,.2f')
        ]
    )
    
    # Add line 
    line = base.mark_line(color='black', strokeWidth=2).encode(
        y='EV Added:Q'
    )
    
    # Add points
    points = base.mark_circle(color='black', size=60).encode(
        y='EV Added:Q'
    )
    
    # Combine charts and configure
    chart = alt.layer(area, line, points).properties(
        title=alt.TitleParams(
            text='EV Added Over Time',
            fontSize=16
        ),
        height=400,
        width='container'
    ).interactive()
    
    return chart

# Main app code
def main():
    # Check if the user is authenticated
    if check_password():
        # Log the page view with IP
        if "username" in st.session_state and "ip_address" in st.session_state:
            log_ip_activity(st.session_state["username"], "page_view_kpis", st.session_state["ip_address"])

        # Display logout button in the sidebar
        st.sidebar.button("Logout", on_click=logout)

        # Display user information
        st.sidebar.info(f"Logged in as: {st.session_state['username']} ({st.session_state['user_role']})")

        # Display IP address (only for admins)
        if st.session_state.get("user_role") == "admin":
            st.sidebar.info(f"Your IP: {st.session_state['ip_address']}")

        # Main app layout
        st.title("📈 KPI Dashboard")
        st.write("Analyze and visualize Key Performance Indicators (KPIs).")
        
        # Load KPI data
        with st.spinner("Loading KPI data from Google Sheets..."):
            df = load_kpi_data()
            
        if df.empty:
            st.error("Failed to load KPI data. Please check your connection to Google Sheets.")
            st.stop()
        
        # Get the available date range
        date_range = df['Week Commencing'].sort_values()
        min_date = date_range.min()
        max_date = date_range.max()
        
        st.success(f"Successfully loaded KPI data from {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")
        
        # Sidebar filters
        st.sidebar.header("Filters")
        
        # Date range selection
        st.sidebar.subheader("Date Range")
        date_filter = st.sidebar.radio(
            "Select date range",
            ["All time", "Last 4 weeks", "Last 12 weeks", "Custom range"]
        )
        
        if date_filter == "All time":
            start_date = min_date
            end_date = max_date
        elif date_filter == "Last 4 weeks":
            end_date = max_date
            start_date = end_date - timedelta(weeks=4)
        elif date_filter == "Last 12 weeks":
            end_date = max_date
            start_date = end_date - timedelta(weeks=12)
        else:  # Custom range
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
            start_date = pd.to_datetime(start_date)
            end_date = pd.to_datetime(end_date)
        
        # Keep date format and interval for backward compatibility with static exports
        date_format = st.sidebar.selectbox(
            "Date format (for exports)",
            ["'%d %b'", "'%Y-%m-%d'", "'%b %Y'"],
            index=0,
            format_func=lambda x: x.replace("'", "")
        )
        
        date_interval = st.sidebar.selectbox(
            "Date interval (for exports)",
            ["weekly", "daily", "monthly"],
            index=0
        )
        
        # Chart options
        st.sidebar.subheader("Chart Options")
        
        # Y-axis limit
        y_limit = st.sidebar.number_input(
            "Y-axis limit (leave blank for auto)",
            min_value=None,
            value=None
        )
        
        # Available KPI metrics
        available_kpis = [
            'New Games Added', 
            'Scrapers added to backlog', 
            'N New Games Played', 
            'Scrapers Done',
            'Scrapers in backlog', 
            'Av. days to model', 
            'Jackpots Played',
            'Jackpots Won', 
            'Jackpots Missed', 
            'Reports Sent', 
            'KPIs recorded',
            'Meetings Run', 
            'Total', 
            'Paused', 
            'Added this week'
        ]
        
        # Let users select which KPIs to display
        st.sidebar.subheader("Select KPIs for Chart")
        selected_kpis = []
        
        # Group metrics into categories for easier selection
        scraper_metrics = [col for col in available_kpis if 'Scraper' in col]
        game_metrics = [col for col in available_kpis if 'Game' in col or 'Jackpot' in col]
        other_metrics = [col for col in available_kpis if col not in scraper_metrics and col not in game_metrics]
        
        with st.sidebar.expander("Scraper Metrics", expanded=True):
            for col in scraper_metrics:
                if col in df.columns:
                    if st.checkbox(col, value=True):
                        selected_kpis.append(col)
        
        with st.sidebar.expander("Game Metrics", expanded=True):
            for col in game_metrics:
                if col in df.columns:
                    if st.checkbox(col, value=True):
                        selected_kpis.append(col)
        
        with st.sidebar.expander("Other Metrics", expanded=False):
            for col in other_metrics:
                if col in df.columns:
                    if st.checkbox(col, value=False):
                        selected_kpis.append(col)
        
        # Display data in tabs
        tab1, tab2, tab3 = st.tabs(["📊 Charts", "📋 Raw Data", "📂 Export"])
        
        with tab1:
            # First display the stacked area chart with selected KPIs
            st.subheader("KPI Metrics Over Time")
            if selected_kpis:
                # Create interactive chart with Altair
                interactive_chart = create_interactive_stacked_area_chart(
                    df,
                    columns=selected_kpis,
                    start_date=start_date,
                    end_date=end_date,
                    y_limit=y_limit
                )
                
                if interactive_chart:
                    # Add a toggle for chart type
                    chart_type = st.radio(
                        "Chart Type",
                        ["Interactive (Altair)", "Static (Matplotlib)", "Simple (Streamlit)"],
                        horizontal=True,
                        key="kpi_chart_type"
                    )
                    
                    if chart_type == "Interactive (Altair)" and interactive_chart is not None:
                        try:
                            st.altair_chart(interactive_chart, use_container_width=True)
                            
                            # Add information about interactivity features
                            st.info("💡 **Interactive Features:** Click and drag to zoom, double-click to reset, hover for details, click legend items to show/hide metrics.")
                        except Exception as e:
                            st.error(f"Error rendering Altair chart: {str(e)}")
                            st.info("Falling back to Matplotlib chart...")
                            chart_type = "Static (Matplotlib)"
                    
                    if chart_type == "Static (Matplotlib)":
                        # Create a static matplotlib chart using the existing function
                        static_chart = create_static_stacked_area_chart(
                            df,
                            columns=selected_kpis,
                            start_date=start_date,
                            end_date=end_date,
                            date_format=date_format.replace("'", ""),
                            date_interval=date_interval,
                            y_limit=y_limit
                        )
                        
                        if static_chart:
                            st.pyplot(static_chart)
                    
                    elif chart_type == "Simple (Streamlit)":
                        # Use Streamlit's built-in chart
                        filtered_df = df[(df['Week Commencing'] >= start_date) & (df['Week Commencing'] <= end_date)].copy()
                        
                        # Keep only selected KPIs
                        existing_columns = [col for col in selected_kpis if col in filtered_df.columns]
                        if existing_columns:
                            filtered_df = filtered_df[['Week Commencing'] + existing_columns].set_index('Week Commencing')
                            st.area_chart(filtered_df, use_container_width=True)
                    
                    # Option to upload to Slack (need to create static version for this)
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        slack_message = st.text_input(
                            "Slack message (optional)",
                            value="KPI Metrics Chart"
                        )
                    with col2:
                        if st.button("Upload to Slack", key="upload_kpi"):
                            # Create a static version for export
                            static_chart = create_static_stacked_area_chart(
                                df,
                                columns=selected_kpis,
                                start_date=start_date,
                                end_date=end_date,
                                date_format=date_format.replace("'", ""),
                                date_interval=date_interval,
                                y_limit=y_limit
                            )
                            
                            if static_chart:
                                # Save chart to a temporary file
                                chart_file = "kpi_chart.png"
                                static_chart.savefig(
                                    chart_file,
                                    bbox_inches='tight',
                                    dpi=300,
                                    facecolor='white',
                                    edgecolor='none'
                                )
                                
                                # Upload to Slack
                                upload_success = upload_to_slack(chart_file, slack_message)
                                if upload_success:
                                    st.success("Chart uploaded to Slack successfully!")
                                else:
                                    st.error("Failed to upload chart to Slack.")
            else:
                st.warning("Please select at least one KPI metric to display.")
            
            # Display EV Added chart if the column exists
            if 'EV Added' in df.columns:
                st.subheader("EV Added Over Time")
                
                # Create interactive EV Added chart with Altair
                interactive_ev_chart = create_interactive_ev_added_chart(
                    df,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if interactive_ev_chart:
                        # Debug information to show what's being plotted
                    with st.expander("Debug EV Added Data", expanded=False):
                        debug_df = df[(df['Week Commencing'] >= start_date) & (df['Week Commencing'] <= end_date)].copy()
                        debug_df = debug_df[['Week Commencing', 'EV Added']].sort_values('Week Commencing')
                        st.write("EV Added values being plotted:")
                        st.dataframe(debug_df)
                        
                        # Show stats
                        non_zero = (debug_df['EV Added'] > 0).sum()
                        total = len(debug_df)
                        st.write(f"Non-zero values: {non_zero} out of {total} rows")
                        st.write(f"Sum of EV Added: £{debug_df['EV Added'].sum():,.2f}")
                        st.write(f"Max EV Added: £{debug_df['EV Added'].max():,.2f}")
                    
                    # Add a toggle for chart type
                    chart_type = st.radio(
                        "Chart Type",
                        ["Interactive (Altair)", "Static (Matplotlib)", "Simple (Streamlit)"],
                        horizontal=True,
                        key="ev_chart_type"
                    )
                    
                    if chart_type == "Interactive (Altair)" and interactive_ev_chart is not None:
                        try:
                            st.altair_chart(interactive_ev_chart, use_container_width=True)
                        except Exception as e:
                            st.error(f"Error rendering Altair chart: {str(e)}")
                            st.info("Falling back to Matplotlib chart...")
                            chart_type = "Static (Matplotlib)"
                    
                    if chart_type == "Static (Matplotlib)":
                        # Create a static matplotlib chart
                        fig, ax = plt.subplots(figsize=(8, 2))
                        
                        # Get the filtered data
                        filtered_df = df[(df['Week Commencing'] >= start_date) & (df['Week Commencing'] <= end_date)].copy()
                        filtered_df = filtered_df[['Week Commencing', 'EV Added']].sort_values('Week Commencing')
                        filtered_df['EV Added'] = pd.to_numeric(filtered_df['EV Added'], errors='coerce').fillna(0)
                        
                        # Plot the data
                        ax.plot(
                            filtered_df['Week Commencing'],
                            filtered_df['EV Added'],
                            marker='o',
                            linestyle='-',
                            color='black',
                            linewidth=2,
                            markersize=8
                        )
                        
                        # Fill the area
                        ax.fill_between(
                            filtered_df['Week Commencing'],
                            filtered_df['EV Added'],
                            color='goldenrod',
                            alpha=0.6
                        )
                        
                        # Format the chart
                        ax.set_title('EV Added Over Time', fontsize=16)
                        ax.set_xlabel('Week Commencing', fontsize=12)
                        ax.set_ylabel('EV Added (£)', fontsize=12)
                        ax.grid(True, linestyle='--', alpha=0.7)
                        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
                        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f'£{x:,.0f}'))
                        plt.xticks(rotation=45)
                        plt.tight_layout()
                        
                        # Display the matplotlib chart
                        st.pyplot(fig)
                    
                    elif chart_type == "Simple (Streamlit)":
                        # Use Streamlit's built-in chart
                        filtered_df = df[(df['Week Commencing'] >= start_date) & (df['Week Commencing'] <= end_date)].copy()
                        filtered_df = filtered_df[['Week Commencing', 'EV Added']].sort_values('Week Commencing')
                        filtered_df['EV Added'] = pd.to_numeric(filtered_df['EV Added'], errors='coerce').fillna(0)
                        filtered_df.set_index('Week Commencing', inplace=True)
                        
                        # Display with Streamlit's built-in chart
                        st.line_chart(filtered_df['EV Added'], use_container_width=True)
                    
                    # Option to upload to Slack (need to create static version for this)
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        slack_message = st.text_input(
                            "Slack message (optional)",
                            value="EV Added Chart"
                        )
                    with col2:
                        if st.button("Upload to Slack", key="upload_ev"):
                            # Create a static version for export
                            static_ev_chart = create_static_ev_added_chart(
                                df,
                                start_date=start_date,
                                end_date=end_date,
                                date_format=date_format.replace("'", ""),
                                date_interval=date_interval
                            )
                            
                            if static_ev_chart:
                                # Save chart to a temporary file
                                chart_file = "ev_chart.png"
                                static_ev_chart.savefig(
                                    chart_file,
                                    bbox_inches='tight',
                                    dpi=50,
                                    facecolor='white',
                                    edgecolor='none'
                                )
                                
                                # Upload to Slack
                                upload_success = upload_to_slack(chart_file, slack_message)
                                if upload_success:
                                    st.success("Chart uploaded to Slack successfully!")
                                else:
                                    st.error("Failed to upload chart to Slack.")
        
        with tab2:
            # Display raw data with filters
            st.subheader("Raw KPI Data")
            
            # Filter data based on date range
            filtered_df = df[
                (df['Week Commencing'] >= start_date) & 
                (df['Week Commencing'] <= end_date)
            ].copy()
            
            # Sort by date
            filtered_df = filtered_df.sort_values('Week Commencing', ascending=False)
            
            # Column selection
            with st.expander("Select Columns to Display", expanded=False):
                all_columns = df.columns.tolist()
                selected_columns = st.multiselect(
                    "Select columns",
                    all_columns,
                    default=['Week Commencing'] + selected_kpis
                )
            
            if not selected_columns:
                selected_columns = ['Week Commencing'] + (selected_kpis if selected_kpis else [])
            
            # Make sure selected columns exist in the dataframe
            display_columns = [col for col in selected_columns if col in filtered_df.columns]
            
            if not display_columns:
                st.warning("No columns selected for display.")
            else:
                # Format the Week Commencing column for display
                if 'Week Commencing' in display_columns:
                    filtered_df['Week Commencing'] = filtered_df['Week Commencing'].dt.strftime('%Y-%m-%d')
                
                # Display the filtered dataframe
                st.dataframe(
                    filtered_df[display_columns],
                    use_container_width=True
                )
        
        with tab3:
            # Export options
            st.subheader("Export Data")
            
            # Filter data based on date range
            export_df = df[
                (df['Week Commencing'] >= start_date) & 
                (df['Week Commencing'] <= end_date)
            ].copy()
            
            # Format date for export
            export_df['Week Commencing'] = export_df['Week Commencing'].dt.strftime('%Y-%m-%d')
            
            # Download as CSV
            st.download_button(
                label="Download as CSV",
                data=export_df.to_csv(index=False).encode('utf-8'),
                file_name=f"kpi_data_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
            
            # Download as Excel
            try:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    export_df.to_excel(writer, sheet_name='KPI Data', index=False)
                    # Auto-adjust columns' width
                    for column in export_df:
                        column_width = max(export_df[column].astype(str).map(len).max(), len(column))
                        col_idx = export_df.columns.get_loc(column)
                        writer.sheets['KPI Data'].set_column(col_idx, col_idx, column_width)
                
                buffer.seek(0)
                
                st.download_button(
                    label="Download as Excel",
                    data=buffer,
                    file_name=f"kpi_data_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(f"Error creating Excel file: {str(e)}")
            
    else:
        st.warning("Please log in to access the KPI dashboard.")

if __name__ == "__main__":
    main()
