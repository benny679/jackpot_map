import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
import json

# Page configuration
st.set_page_config(page_title="Global Tax Data Dashboard", layout="wide")

# Title and description
st.title("Global Tax Data Dashboard")
st.markdown("Interactive map of global tax data. Click on countries or filter by region to view detailed tax information.")

# Function to load data from Google Sheet
@st.cache_data(ttl=600)  # Cache data for 10 minutes
def load_data():
    try:
        # Method 1: Using secrets.toml for authentication
        # Create credentials from secrets
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        
        # Connect to the spreadsheet
        gc = gspread.authorize(credentials)
        sheet = gc.open_by_key('1SihEq-fymsko-2vr1NTaNG6NNTC_gBf9OMnI2pUmFEo')
        worksheet = sheet.worksheet("Tax")  # Change this to your actual sheet name
        
        # Get all data and convert to DataFrame
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # If the above method fails, try direct URL as fallback
        if df.empty:
            url = "https://docs.google.com/spreadsheets/d/1SihEq-fymsko-2vr1NTaNG6NNTC_gBf9OMnI2pUmFEo/export?format=csv&gid=978503341"
            df = pd.read_csv(url)
        
        return df
    
    except Exception as e:
        st.error(f"Error loading data: {e}")
        
        # If both methods fail, use sample data for demonstration
        st.warning("Using sample data for demonstration. Please check your Google Sheet permissions.")
        # Create sample data with common tax data fields
        sample_data = {
            'Country': ['United States', 'Canada', 'United Kingdom', 'Germany', 'France', 
                        'Japan', 'Australia', 'China', 'Brazil', 'India'],
            'Region': ['North America', 'North America', 'Europe', 'Europe', 'Europe', 
                      'Asia', 'Oceania', 'Asia', 'South America', 'Asia'],
            'Corporate Tax Rate': [21.0, 15.0, 19.0, 15.8, 28.4, 30.6, 30.0, 25.0, 34.0, 30.0],
            'VAT/Sales Tax': [0.0, 5.0, 20.0, 19.0, 20.0, 10.0, 10.0, 13.0, 17.0, 18.0],
            'Income Tax (Highest)': [37.0, 33.0, 45.0, 45.0, 45.0, 45.0, 45.0, 45.0, 27.5, 30.0],
            'Year': [2023, 2023, 2023, 2023, 2023, 2023, 2023, 2023, 2023, 2023]
        }
        return pd.DataFrame(sample_data)

# Load data
df = load_data()

# Sidebar filters
st.sidebar.header("Filters")

# Region filter
all_regions = sorted(df['Region'].unique())
selected_regions = st.sidebar.multiselect("Select Regions", all_regions, default=all_regions)

# Filter data based on selection
filtered_df = df[df['Region'].isin(selected_regions)]

# Year filter if available
if 'Year' in df.columns:
    years = sorted(df['Year'].unique())
    selected_year = st.sidebar.selectbox("Select Year", years, index=len(years)-1)
    filtered_df = filtered_df[filtered_df['Year'] == selected_year]

# Create tabs
tab1, tab2 = st.tabs(["Map View", "Table View"])

# Map view
with tab1:
    # Determine which tax column to display
    tax_columns = [col for col in df.columns if 'Tax' in col or 'tax' in col]
    if tax_columns:
        selected_tax = st.selectbox("Select Tax Measure to Display", tax_columns)
    else:
        selected_tax = df.columns[2]  # Default to third column if no tax columns found
    
    # Configure map
    fig = px.choropleth(
        filtered_df,
        locations="Country",  # Column containing country names
        locationmode="country names",  # Use country names (alternative is ISO codes)
        color=selected_tax,
        hover_name="Country",
        hover_data=[col for col in filtered_df.columns if col != "Country"],
        color_continuous_scale=px.colors.sequential.Blues,
        title=f"{selected_tax} by Country"
    )
    
    fig.update_layout(
        height=600,
        margin={"r": 0, "t": 30, "l": 0, "b": 0},
        coloraxis_colorbar={
            'title': selected_tax
        }
    )
    
    # Display map
    st.plotly_chart(fig, use_container_width=True)
    
    # Country details on click
    st.subheader("Country Details")
    st.info("Click on a country in the map to see detailed information")
    
    # JavaScript callback for clicks
    selected_countries = []
    clickData = st.session_state.get('clickData', None)
    
    if clickData:
        point = clickData['points'][0]
        country_name = point['location']
        selected_countries = [country_name]
        
    # Alternative selection method
    if not selected_countries:
        selected_country = st.selectbox("Or select a country", sorted(filtered_df['Country'].unique()))
        if selected_country:
            selected_countries = [selected_country]
    
    # Display selected country data
    if selected_countries:
        country_data = filtered_df[filtered_df['Country'].isin(selected_countries)]
        
        if not country_data.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader(country_data['Country'].iloc[0])
                st.markdown(f"**Region:** {country_data['Region'].iloc[0]}")
                
                # Display tax metrics
                for col in tax_columns:
                    st.metric(col, f"{country_data[col].iloc[0]}%")
            
            with col2:
                # Bar chart comparing with regional average
                region = country_data['Region'].iloc[0]
                region_data = filtered_df[filtered_df['Region'] == region]
                
                comparison_data = []
                for tax in tax_columns:
                    country_val = country_data[tax].iloc[0]
                    region_avg = region_data[tax].mean()
                    
                    comparison_data.append({
                        'Metric': tax,
                        'Country': country_val,
                        'Regional Average': region_avg
                    })
                
                comparison_df = pd.DataFrame(comparison_data)
                
                # Reshape for plotting
                plot_df = pd.melt(
                    comparison_df, 
                    id_vars=['Metric'], 
                    value_vars=['Country', 'Regional Average'],
                    var_name='Type', 
                    value_name='Rate'
                )
                
                fig = px.bar(
                    plot_df, 
                    x='Metric', 
                    y='Rate', 
                    color='Type',
                    barmode='group',
                    title=f"Comparison with {region} Average"
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            # Link to dashboard
            st.markdown("---")
            if st.button("Back to Main Dashboard"):
                st.experimental_set_query_params(
                    page="dashboard",
                    country=country_data['Country'].iloc[0]
                )
                # For actual navigation, you would use:
                # st.script_runner.rerun()

# Table view
with tab2:
    st.header("Tax Data Table")
    
    # Search functionality
    search = st.text_input("Search for a country")
    if search:
        display_df = filtered_df[filtered_df['Country'].str.contains(search, case=False)]
    else:
        display_df = filtered_df
        
    # Display table
    st.dataframe(display_df, use_container_width=True)
    
    # Export functionality
    if st.button("Export Data"):
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download CSV",
            csv,
            "tax_data.csv",
            "text/csv",
            key='download-csv'
        )

# Footer
st.markdown("---")
st.markdown("Data source: [Google Sheets](https://docs.google.com/spreadsheets/d/1SihEq-fymsko-2vr1NTaNG6NNTC_gBf9OMnI2pUmFEo/edit)")
