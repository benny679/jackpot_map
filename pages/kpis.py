import streamlit as st
import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import io
import os

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
            # Check if the column contains string values before trying to replace characters
            if df['EV Added'].dtype == 'object':
                df['EV Added'] = df['EV Added'].str.replace('£', '').str.replace(',', '')
            df['EV Added'] = pd.to_numeric(df['EV Added'], errors='coerce')

        # Convert Week Commencing to datetime
        if 'Week Commencing' in df.columns:
            df['Week Commencing'] = pd.to_datetime(df['Week Commencing'], format='%d/%m/%Y', errors='coerce')

        return df
    except Exception as e:
        st.error(f"Error loading KPI data: {str(e)}")
        return pd.DataFrame()

# Function to create an interactive stacked area chart using Plotly
def create_stacked_area_chart(df, columns, start_date=None, end_date=None, date_format=None, date_interval=None, y_limit=None):
    """
    Create an interactive stacked area chart with selected KPIs using Plotly.
    
    Parameters:
        df (DataFrame): The data to plot
        columns (list): List of columns to include in the chart
        start_date (datetime, optional): Start date for x-axis
        end_date (datetime, optional): End date for x-axis
        date_format (str, optional): Not used in Plotly (handled by Plotly's configuration)
        date_interval (str, optional): Not used in Plotly (handled by Plotly's configuration)
        y_limit (float, optional): Optional upper limit for y-axis
    """
    # Specify colors for the chart
    colors = ['#ffd700', '#0084ff', '#04ff00', '#ff3c00', '#ff0084', '#9932CC', '#00CED1', '#FFA07A']
    
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
    
    # Create the figure
    fig = go.Figure()
    
    # Add traces for each KPI
    for i, col in enumerate(existing_columns):
        fig.add_trace(
            go.Scatter(
                x=df['Week Commencing'],
                y=df[col].fillna(0),
                mode='lines',
                name=col,
                line=dict(width=0),
                stackgroup='one',  # This makes it a stacked area chart
                fillcolor=colors[i % len(colors)],
                hovertemplate='%{x}<br>%{y:,.0f}<extra>' + col + '</extra>'
            )
        )
    
    # Update layout
    fig.update_layout(
        title='KPI Metrics Over Time',
        title_font_size=18,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hovermode='x unified',
        xaxis=dict(
            title='Week Commencing',
            tickformat='%d %b %Y',
            rangeslider_visible=True
        ),
        yaxis=dict(
            title='Value',
            rangemode='nonnegative',
            range=[0, y_limit] if y_limit else None,
            tickformat=',d'
        ),
        height=500,
        margin=dict(l=40, r=40, t=60, b=40)
    )
    
    return fig

# Function to create an interactive EV Added chart using Plotly
def create_ev_added_chart(df, start_date=None, end_date=None, date_format=None, date_interval=None):
    """
    Create an interactive chart for EV Added over time using Plotly.
    
    Parameters:
        df (DataFrame): The data to plot
        start_date (datetime, optional): Start date for x-axis
        end_date (datetime, optional): End date for x-axis
        date_format (str, optional): Not used in Plotly (handled by Plotly's configuration)
        date_interval (str, optional): Not used in Plotly (handled by Plotly's configuration)
    """
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
    df = df[(df['Week Commencing'] >= start_date) & (df['Week Commencing'] <= end_date)]
    
    # Create the figure
    fig = go.Figure()
    
    # Add area fill for EV Added
    fig.add_trace(
        go.Scatter(
            x=df['Week Commencing'],
            y=df['EV Added'].fillna(0),
            mode='lines',
            name='EV Added',
            fill='tozeroy',
            line=dict(color='black', width=1),
            fillcolor='#DAA520',  # Golden color
            hovertemplate='%{x}<br>£%{y:,.2f}<extra>EV Added</extra>'
        )
    )
    
    # Add markers for data points
    fig.add_trace(
        go.Scatter(
            x=df['Week Commencing'],
            y=df['EV Added'].fillna(0),
            mode='markers',
            name='',
            marker=dict(color='black', size=8),
            showlegend=False,
            hoverinfo='skip'
        )
    )
    
    # Update layout
    fig.update_layout(
        title='EV Added Over Time',
        title_font_size=18,
        hovermode='x unified',
        xaxis=dict(
            title='Week Commencing',
            tickformat='%d %b %Y',
            rangeslider_visible=True
        ),
        yaxis=dict(
            title='EV Added (£)',
            rangemode='nonnegative',
            tickprefix='£',
            tickformat=',.0f'
        ),
        height=500,
        margin=dict(l=40, r=40, t=60, b=40)
    )
    
    return fig

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
        
        # Keep date format and interval for backward compatibility, but they're not used in Plotly
        date_format = st.sidebar.selectbox(
            "Date format",
            ["'%d %b'", "'%Y-%m-%d'", "'%b %Y'"],
            index=0,
            format_func=lambda x: x.replace("'", "")
        )
        
        date_interval = st.sidebar.selectbox(
            "Date interval",
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
        st.sidebar.subheader("Select KPIs for Stacked Chart")
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
                stacked_fig = create_stacked_area_chart(
                    df,
                    columns=selected_kpis,
                    start_date=start_date,
                    end_date=end_date,
                    y_limit=y_limit
                )
                
                if stacked_fig:
                    # Display the interactive plot
                    st.plotly_chart(stacked_fig, use_container_width=True)
                    
                    # Option to upload to Slack
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        slack_message = st.text_input(
                            "Slack message (optional)",
                            value="KPI Metrics Chart"
                        )
                    with col2:
                        if st.button("Upload to Slack", key="upload_kpi"):
                            # Save chart to a temporary file
                            chart_file = "kpi_chart.png"
                            stacked_fig.write_image(
                                chart_file,
                                width=1200,
                                height=600,
                                scale=2
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
                ev_fig = create_ev_added_chart(
                    df,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if ev_fig:
                    # Display the interactive plot
                    st.plotly_chart(ev_fig, use_container_width=True)
                    
                    # Option to upload to Slack
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        slack_message = st.text_input(
                            "Slack message (optional)",
                            value="EV Added Chart"
                        )
                    with col2:
                        if st.button("Upload to Slack", key="upload_ev"):
                            # Save chart to a temporary file
                            chart_file = "ev_chart.png"
                            ev_fig.write_image(
                                chart_file,
                                width=1200,
                                height=600,
                                scale=2
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
