import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2 import service_account
import json

# Page configuration
st.set_page_config(page_title="Global iGaming Regulation & Tax Map", layout="wide")

# Title and description
st.title("Global iGaming Regulation & Tax Dashboard")
st.markdown("Interactive map of global iGaming regulations and tax data. Click on countries or filter by region to view detailed information.")

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
        worksheet = sheet.worksheet("Sheet1")  # Change this to your actual sheet name
        
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
        # Create sample data with common iGaming regulation & tax data fields
        sample_data = {
            'Country_region': ['United States', 'Canada', 'United Kingdom', 'Germany', 'France', 
                      'Japan', 'Australia', 'China', 'Brazil', 'India'],
            'Market_region': ['North America', 'North America', 'Europe', 'Europe', 'Europe', 
                      'Asia', 'Oceania', 'Asia', 'South America', 'Asia'],
            'GGR CAGR': [15.2, 12.1, 8.5, 7.2, 6.8, 5.3, 10.2, 3.5, 18.7, 22.4],
            'Regulated': ['Yes', 'Yes', 'Yes', 'Yes', 'Yes', 'No', 'Yes', 'No', 'Partially', 'No'],
            'Regulation_type': ['State-level', 'Provincial', 'National', 'National', 'National', 
                         'Prohibited', 'National', 'Prohibited', 'Transition', 'Limited'],
            'Offshore?': ['Yes', 'Yes', 'No', 'No', 'No', 'Yes', 'Yes', 'Yes', 'Yes', 'Yes'],
            'Residents?': ['Yes', 'Yes', 'Yes', 'Yes', 'Yes', 'No', 'Yes', 'No', 'Yes', 'Restricted'],
            'Casino': ['Regulated', 'Regulated', 'Regulated', 'Regulated', 'Regulated', 
                    'Prohibited', 'Regulated', 'Prohibited', 'Partially', 'Prohibited'],
            'iGaming': ['Regulated', 'Regulated', 'Regulated', 'Regulated', 'Regulated', 
                     'Prohibited', 'Regulated', 'Prohibited', 'Partially', 'Prohibited'],
            'Betting': ['Regulated', 'Regulated', 'Regulated', 'Regulated', 'Regulated', 
                     'Limited', 'Regulated', 'State-Run', 'Regulated', 'Limited'],
            'iBetting': ['Regulated', 'Regulated', 'Regulated', 'Regulated', 'Regulated', 
                      'Limited', 'Regulated', 'State-Run', 'Regulated', 'Limited'],
            'Operator_tax': [25.0, 20.0, 15.0, 5.3, 13.2, 0.0, 10.0, 20.0, 18.0, 30.0],
            'Player_tax': [0.0, 0.0, 0.0, 5.0, 12.0, 15.0, 0.0, 20.0, 0.0, 30.0],
            'Accounts_#': [1500000, 890000, 3200000, 2100000, 1800000, 
                         120000, 950000, 0, 1200000, 350000],
            'Tax (iGaming)': [25.0, 20.0, 15.0, 5.3, 13.2, 0.0, 10.0, 20.0, 18.0, 30.0],
            'Legality/Regulation': ['Legal/Regulated', 'Legal/Regulated', 'Legal/Regulated', 
                                  'Legal/Regulated', 'Legal/Regulated', 'Illegal', 
                                  'Legal/Regulated', 'Illegal', 'Legal/Partially Regulated', 'Restricted']
        }
        return pd.DataFrame(sample_data)

# Load data
df = load_data()

# Sidebar filters
st.sidebar.header("Filters")

# Market region filter
all_market_regions = sorted(df['Market_region'].unique())
selected_market_regions = st.sidebar.multiselect("Select Market Regions", all_market_regions, default=all_market_regions)

# Regulation type filter
all_regulation_types = sorted(df['Regulation_type'].unique())
selected_regulation_types = st.sidebar.multiselect("Select Regulation Types", all_regulation_types, default=all_regulation_types)

# Filter data based on selection
filtered_df = df[
    (df['Market_region'].isin(selected_market_regions)) &
    (df['Regulation_type'].isin(selected_regulation_types))
]

# Create tabs
tab1, tab2, tab3 = st.tabs(["Regulation Map", "Tax Map", "Data Table"])

# Regulation Map view
with tab1:
    st.header("iGaming Regulation by Country")
    
    # Color coding for regulation status
    if 'Regulated' in df.columns:
        fig = px.choropleth(
            filtered_df,
            locations="Country_region",  # Column containing country names
            locationmode="country names",  # Use country names (alternative is ISO codes)
            color="Regulated",  # Color by regulation status
            hover_name="Country_region",
            hover_data=["Market_region", "Regulation_type", "Offshore?", "Casino", "iGaming", "Betting", "iBetting"],
            color_discrete_map={
                "Yes": "#2E8B57",       # Green for fully regulated
                "Partially": "#FFA500",  # Orange for partially regulated
                "No": "#B22222"         # Red for not regulated
            },
            title="iGaming Regulation Status by Country"
        )
    else:
        # Alternative coloring by Legality/Regulation
        fig = px.choropleth(
            filtered_df,
            locations="Country_region",
            locationmode="country names",
            color="Legality/Regulation",
            hover_name="Country_region",
            hover_data=["Market_region", "Regulation_type", "Offshore?", "Casino", "iGaming", "Betting", "iBetting"],
            color_discrete_sequence=px.colors.qualitative.Safe,
            title="iGaming Regulation Status by Country"
        )
    
    fig.update_layout(
        height=600,
        margin={"r": 0, "t": 30, "l": 0, "b": 0},
    )
    
    # Display map
    st.plotly_chart(fig, use_container_width=True)
    
    # Filter for specific gaming types
    gaming_types = ["Casino", "iGaming", "Betting", "iBetting"]
    selected_gaming_type = st.selectbox("View regulation status for specific type:", gaming_types)
    
    # Create a map for the selected gaming type
    fig_gaming = px.choropleth(
        filtered_df,
        locations="Country_region",
        locationmode="country names",
        color=selected_gaming_type,  # Color by selected gaming type status
        hover_name="Country_region",
        hover_data=["Market_region", "Regulation_type", selected_gaming_type],
        color_discrete_sequence=px.colors.qualitative.Safe,
        title=f"{selected_gaming_type} Regulation Status by Country"
    )
    
    fig_gaming.update_layout(
        height=500,
        margin={"r": 0, "t": 30, "l": 0, "b": 0},
    )
    
    st.plotly_chart(fig_gaming, use_container_width=True)

# Tax Map view
with tab2:
    st.header("iGaming Tax Rates by Country")
    
    # Choose between operator tax and player tax
    tax_type = st.radio("Select Tax Type:", ["Operator_tax", "Player_tax", "Tax (iGaming)"], 
                          format_func=lambda x: x.replace("_", " ").title())
    
    # Create tax rate map
    fig_tax = px.choropleth(
        filtered_df,
        locations="Country_region",
        locationmode="country names",
        color=tax_type,
        hover_name="Country_region",
        hover_data=["Market_region", "Regulated", tax_type],
        color_continuous_scale=px.colors.sequential.Bluyl,
        title=f"{tax_type.replace('_', ' ').title()} by Country",
        labels={tax_type: f"{tax_type.replace('_', ' ').title()} (%)"}
    )
    
    fig_tax.update_layout(
        height=600,
        margin={"r": 0, "t": 30, "l": 0, "b": 0},
        coloraxis_colorbar={
            'title': f"{tax_type.replace('_', ' ').title()} (%)"
        }
    )
    
    st.plotly_chart(fig_tax, use_container_width=True)
    
    # Growth rate (CAGR) map if available
    if 'GGR CAGR' in filtered_df.columns:
        st.subheader("Market Growth (CAGR) by Country")
        
        fig_growth = px.choropleth(
            filtered_df,
            locations="Country_region",
            locationmode="country names",
            color="GGR CAGR",
            hover_name="Country_region",
            hover_data=["Market_region", "Regulated", "GGR CAGR"],
            color_continuous_scale=px.colors.sequential.Viridis,
            title="Gross Gaming Revenue CAGR by Country",
            labels={"GGR CAGR": "Growth Rate (%)"}
        )
        
        fig_growth.update_layout(
            height=500,
            margin={"r": 0, "t": 30, "l": 0, "b": 0},
            coloraxis_colorbar={
                'title': "Growth Rate (%)"
            }
        )
        
        st.plotly_chart(fig_growth, use_container_width=True)

# Country details section (displayed below maps)
st.header("Country Details")
st.info("Click on a country in the map or select from the dropdown to see detailed information")

# Country selection dropdown
selected_country = st.selectbox("Select a country", sorted(filtered_df['Country_region'].unique()))

# Display selected country data
if selected_country:
    country_data = filtered_df[filtered_df['Country_region'] == selected_country]
    
    if not country_data.empty:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader(country_data['Country_region'].iloc[0])
            st.markdown(f"**Market Region:** {country_data['Market_region'].iloc[0]}")
            st.markdown(f"**Regulation Type:** {country_data['Regulation_type'].iloc[0]}")
            st.markdown(f"**Regulated:** {country_data['Regulated'].iloc[0]}")
            
            # Create a metrics card for tax information
            st.subheader("Tax Information")
            col_a, col_b, col_c = st.columns(3)
            
            with col_a:
                if 'Operator_tax' in country_data.columns:
                    st.metric("Operator Tax", f"{country_data['Operator_tax'].iloc[0]}%")
            
            with col_b:
                if 'Player_tax' in country_data.columns:
                    st.metric("Player Tax", f"{country_data['Player_tax'].iloc[0]}%")
            
            with col_c:
                if 'Tax (iGaming)' in country_data.columns:
                    st.metric("iGaming Tax", f"{country_data['Tax (iGaming)'].iloc[0]}%")
            
            # Gaming types regulation status
            st.subheader("Gaming Types")
            for game_type in ["Casino", "iGaming", "Betting", "iBetting"]:
                if game_type in country_data.columns:
                    st.markdown(f"**{game_type}:** {country_data[game_type].iloc[0]}")
        
        with col2:
            # Create a bar chart comparing with regional average
            st.subheader("Comparison with Regional Average")
            
            region = country_data['Market_region'].iloc[0]
            region_data = filtered_df[filtered_df['Market_region'] == region]
            
            # Prepare data for comparison
            tax_columns = ['Operator_tax', 'Player_tax', 'Tax (iGaming)']
            tax_columns = [col for col in tax_columns if col in filtered_df.columns]
            
            comparison_data = []
            for tax in tax_columns:
                country_val = country_data[tax].iloc[0]
                region_avg = region_data[tax].mean()
                
                comparison_data.append({
                    'Metric': tax.replace('_', ' ').title(),
                    f'{selected_country}': country_val,
                    f'{region} Average': region_avg
                })
            
            comparison_df = pd.DataFrame(comparison_data)
            
            # Reshape for plotting
            plot_df = pd.melt(
                comparison_df, 
                id_vars=['Metric'], 
                value_vars=[f'{selected_country}', f'{region} Average'],
                var_name='Entity', 
                value_name='Tax Rate (%)'
            )
            
            fig = px.bar(
                plot_df, 
                x='Metric', 
                y='Tax Rate (%)', 
                color='Entity',
                barmode='group',
                title=f"Tax Comparison with {region} Average"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Player accounts if available
            if 'Accounts_#' in country_data.columns:
                if country_data['Accounts_#'].iloc[0] > 0:
                    st.metric("Registered Player Accounts", f"{int(country_data['Accounts_#'].iloc[0]):,}")
            
            # Growth rate if available
            if 'GGR CAGR' in country_data.columns:
                st.metric("Growth Rate (CAGR)", f"{country_data['GGR CAGR'].iloc[0]}%")
        
        # Link to dashboard
        st.markdown("---")
        if st.button("View in Main Dashboard"):
            # Create query parameters to pass to your dashboard
            st.experimental_set_query_params(
                page="dashboard",
                country=country_data['Country_region'].iloc[0]
            )
            # For actual navigation, you would use:
            # st.script_runner.rerun()

# Table view
with tab3:
    st.header("iGaming Regulations & Tax Data Table")
    
    # Search functionality
    search = st.text_input("Search for a country")
    if search:
        display_df = filtered_df[filtered_df['Country_region'].str.contains(search, case=False)]
    else:
        display_df = filtered_df
        
    # Column selector
    available_columns = list(display_df.columns)
    selected_columns = st.multiselect(
        "Select columns to display",
        available_columns,
        default=["Country_region", "Market_region", "Regulated", "Regulation_type", "Operator_tax", "Player_tax"]
    ) or available_columns  # If nothing selected, show all columns
    
    # Display table
    st.dataframe(display_df[selected_columns], use_container_width=True)
    
    # Export functionality
    if st.button("Export Data"):
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download CSV",
            csv,
            "igaming_data.csv",
            "text/csv",
            key='download-csv'
        )

# Footer
st.markdown("---")
st.markdown("Data source: [Google Sheets](https://docs.google.com/spreadsheets/d/1SihEq-fymsko-2vr1NTaNG6NNTC_gBf9OMnI2pUmFEo/edit)")
