import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2 import service_account

# Function to load data from Google Sheet
@st.cache_data(ttl=600)  # Cache data for 10 minutes
def load_data():
    try:
        # Using secrets.toml for authentication
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
        sheet = gc.open("Research - Summary")  # Open by exact name
        worksheet = sheet.worksheet("Tax")  # Use the Tax worksheet
        
        # Get all values as CSV
        url = f"https://docs.google.com/spreadsheets/d/{sheet.id}/export?format=csv&gid={worksheet.id}"
        
        # Alternative approach: direct CSV download
        st.write("Attempting direct CSV download from your Google Sheet...")
        
        # Use raw requests to download the CSV
        import requests
        headers = {
            'Authorization': f'Bearer {credentials.token}',
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            import io
            # Use pandas to read the CSV directly
            df = pd.read_csv(io.StringIO(response.text))
            st.write("CSV download successful!")
            st.write("Found columns:", df.columns.tolist())
            
            # Clean column names (strip whitespace, special chars)
            df.columns = [str(col).strip() for col in df.columns]
            
            # Check for required columns
            required_cols = ["Country_region", "Market_region"]
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                st.warning(f"Missing required columns: {missing_cols}")
                
                # Manual column selection
                st.write("Please select which columns to use for country and region:")
                col1, col2 = st.columns(2)
                
                with col1:
                    country_col = st.selectbox(
                        "Select column for Country:",
                        options=df.columns,
                        index=0
                    )
                    
                    # Create Country_region if missing
                    if "Country_region" not in df.columns:
                        df["Country_region"] = df[country_col]
                
                with col2:
                    region_options = [col for col in df.columns if col != country_col]
                    region_col = st.selectbox(
                        "Select column for Region:",
                        options=region_options,
                        index=0
                    )
                    
                    # Create Market_region if missing
                    if "Market_region" not in df.columns:
                        df["Market_region"] = df[region_col]
            
            # Convert likely numeric columns
            for col in df.columns:
                # Check if column name suggests it's numeric
                if any(term in col.lower() for term in ["tax", "cagr", "rate", "%", "accounts"]):
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
        else:
            st.error(f"Failed to download CSV: {response.status_code} {response.reason}")
            raise Exception(f"CSV download failed: {response.status_code}")
            
        # Fallback to traditional approach if needed
        st.write("Couldn't download as CSV, trying alternative method...")        
        all_values = worksheet.get_all_values()
        
        # Ask user to input expected header information
        st.write("Please enter your expected headers (comma separated):")
        header_input = st.text_input("Headers", "Country_region,Market_region,Legality/Regulation,Tax (iGaming),Regulated,Operator_tax")
        expected_headers = [h.strip() for h in header_input.split(",")]
        
        # Create a DataFrame with expected headers
        data_rows = all_values[1:]  # Skip the header row
        df = pd.DataFrame(data_rows)
        
        # Assign custom headers
        if len(df.columns) >= len(expected_headers):
            # Assign the provided headers to the first columns
            df.columns = expected_headers + [f"Column_{i}" for i in range(len(expected_headers), len(df.columns))]
        else:
            # If there are more headers than columns, use what fits
            df.columns = expected_headers[:len(df.columns)]
        
        return df
    
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.error("Please check your Google Sheet permissions and ensure the 'Research - Summary' sheet with 'Tax' worksheet exists.")
        # Raise the exception to see detailed error message during development
        raise e

# Page configuration
st.set_page_config(page_title="Global iGaming Regulation & Tax Map", layout="wide")

# Title and description
st.title("Global iGaming Regulation & Tax Dashboard")
st.markdown("Interactive map of global iGaming regulations and tax data. Click on countries or filter by region to view detailed information.")

# Load data
df = load_data()

# Sidebar filters
st.sidebar.header("Filters")

# Show column names for debugging
st.sidebar.expander("Debug Information").write(df.columns.tolist())

# Market region filter - with safety check
if 'Market_region' in df.columns and not df['Market_region'].isna().all():
    all_market_regions = sorted(df['Market_region'].unique())
    selected_market_regions = st.sidebar.multiselect("Select Market Regions", all_market_regions, default=all_market_regions)
    
    # Filter data based on selection
    filtered_df = df[df['Market_region'].isin(selected_market_regions)]
else:
    st.sidebar.warning("Market_region column not found or is empty.")
    filtered_df = df  # Use unfiltered data

# Regulation type filter
if 'Regulation_type' in df.columns and not df['Regulation_type'].isna().all():
    all_regulation_types = sorted(df['Regulation_type'].unique())
    selected_regulation_types = st.sidebar.multiselect("Select Regulation Types", all_regulation_types, default=all_regulation_types)
    
    # Filter data based on selection
    filtered_df = filtered_df[filtered_df['Regulation_type'].isin(selected_regulation_types)]

# Priority region filter
if 'Priority region' in df.columns and not df['Priority region'].isna().all():
    priority_options = ['All', 'Priority Only', 'Non-Priority Only']
    priority_filter = st.sidebar.radio("Priority Regions", priority_options)
    
    if priority_filter == 'Priority Only':
        filtered_df = filtered_df[filtered_df['Priority region'] == 'Yes']
    elif priority_filter == 'Non-Priority Only':
        filtered_df = filtered_df[filtered_df['Priority region'] != 'Yes']

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs(["Regulation Map", "Tax Map", "Responsible Gambling", "Data Table"])

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
    gaming_types = [g for g in gaming_types if g in df.columns]
    if gaming_types:
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
    tax_options = []
    if "Operator_tax" in df.columns:
        tax_options.append("Operator_tax")
    if "Player_tax" in df.columns:
        tax_options.append("Player_tax")
    if "Tax (iGaming)" in df.columns:
        tax_options.append("Tax (iGaming)")
    
    if tax_options:
        tax_type = st.radio("Select Tax Type:", tax_options, 
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
    else:
        st.info("No tax rate data available in the dataset.")
    
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

# Responsible Gambling view
with tab3:
    st.header("Responsible Gambling Measures by Country")
    
    # Check if the responsible gambling columns exist
    rg_columns = [col for col in df.columns if col in ['Responsible Gambling (iGaming)', 'Stake_limit', 'Deposit_limit', 'Withdrawal_limit']]
    
    if 'Responsible Gambling (iGaming)' in rg_columns:
        # If there's a general RG score column
        fig_rg = px.choropleth(
            filtered_df,
            locations="Country_region",
            locationmode="country names",
            color="Responsible Gambling (iGaming)",
            hover_name="Country_region",
            hover_data=["Market_region", "Regulated"],
            color_continuous_scale=px.colors.sequential.Greens,
            title="Responsible Gambling Score by Country"
        )
        
        fig_rg.update_layout(
            height=600,
            margin={"r": 0, "t": 30, "l": 0, "b": 0}
        )
        
        st.plotly_chart(fig_rg, use_container_width=True)
    
    # Specific Responsible Gambling measures
    rg_measures = [col for col in ['Stake_limit', 'Deposit_limit', 'Withdrawal_limit'] if col in df.columns]
    
    if rg_measures:
        st.subheader("Responsible Gambling Measures")
        selected_measure = st.selectbox("Select Measure", rg_measures)
        
        # Create a map for the selected measure
        fig_measure = px.choropleth(
            filtered_df,
            locations="Country_region",
            locationmode="country names",
            color=selected_measure,
            hover_name="Country_region",
            hover_data=["Market_region", selected_measure],
            color_discrete_sequence=px.colors.qualitative.Safe,
            title=f"{selected_measure.replace('_', ' ').title()} Requirements by Country"
        )
        
        fig_measure.update_layout(
            height=500,
            margin={"r": 0, "t": 30, "l": 0, "b": 0}
        )
        
        st.plotly_chart(fig_measure, use_container_width=True)
    
    # If no responsible gambling data is available
    if not rg_columns:
        st.info("No responsible gambling data available in the dataset.")
        
    # Table of RG measures
    if rg_measures:
        st.subheader("Responsible Gambling Measures by Country")
        rg_data = filtered_df[['Country_region', 'Market_region'] + rg_measures]
        st.dataframe(rg_data, use_container_width=True)

# Table view
with tab4:
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

# Country details section (displayed below maps)
st.header("Country Details")
st.info("Click on a country in the map or select from the dropdown to see detailed information")

# Country selection dropdown
if 'Country_region' in filtered_df.columns and not filtered_df.empty:
    country_list = sorted(filtered_df['Country_region'].unique())
    if country_list:
        selected_country = st.selectbox("Select a country", country_list)
    else:
        st.warning("No countries available with the current filters.")
        selected_country = None
else:
    st.error("Country_region column not found in the data.")
    selected_country = None

# Display selected country data
if selected_country:
    country_data = filtered_df[filtered_df['Country_region'] == selected_country]
    
    if not country_data.empty:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader(country_data['Country_region'].iloc[0])
            st.markdown(f"**Market Region:** {country_data['Market_region'].iloc[0]}")
            
            if 'Regulation_type' in country_data.columns:
                st.markdown(f"**Regulation Type:** {country_data['Regulation_type'].iloc[0]}")
            
            if 'Regulated' in country_data.columns:
                st.markdown(f"**Regulated:** {country_data['Regulated'].iloc[0]}")
                
            if 'Legality/Regulation' in country_data.columns:
                st.markdown(f"**Legality/Regulation:** {country_data['Legality/Regulation'].iloc[0]}")
            
            # Create a metrics card for tax information
            st.subheader("Tax Information")
            tax_columns = [col for col in ['Operator_tax', 'Player_tax', 'Tax (iGaming)'] 
                           if col in country_data.columns]
            
            if tax_columns:
                cols = st.columns(len(tax_columns))
                for i, tax_col in enumerate(tax_columns):
                    with cols[i]:
                        st.metric(tax_col.replace('_', ' ').title(), 
                                  f"{country_data[tax_col].iloc[0]}%")
            
            # Gaming types regulation status
            game_types = [col for col in ["Casino", "iGaming", "Betting", "iBetting"] 
                          if col in country_data.columns]
            
            if game_types:
                st.subheader("Gaming Types")
                for game_type in game_types:
                    st.markdown(f"**{game_type}:** {country_data[game_type].iloc[0]}")
                    
            # Responsible gambling info if available
            rg_measures = [col for col in ['Stake_limit', 'Deposit_limit', 'Withdrawal_limit'] 
                           if col in country_data.columns]
            
            if rg_measures:
                st.subheader("Responsible Gambling Measures")
                for measure in rg_measures:
                    if pd.notna(country_data[measure].iloc[0]):
                        st.markdown(f"**{measure.replace('_', ' ').title()}:** {country_data[measure].iloc[0]}")
        
        with col2:
            # Additional information section
            if 'Notes' in country_data.columns and pd.notna(country_data['Notes'].iloc[0]):
                st.subheader("Notes")
                st.write(country_data['Notes'].iloc[0])
                
            if 'Triggering reviews' in country_data.columns and pd.notna(country_data['Triggering reviews'].iloc[0]):
                st.subheader("Triggering Reviews")
                st.write(country_data['Triggering reviews'].iloc[0])
            
            # Create a bar chart comparing with regional average if tax data exists
            tax_columns = [col for col in ['Operator_tax', 'Player_tax', 'Tax (iGaming)'] 
                           if col in country_data.columns]
            
            if tax_columns:
                st.subheader("Comparison with Regional Average")
                
                region = country_data['Market_region'].iloc[0]
                region_data = filtered_df[filtered_df['Market_region'] == region]
                
                # Prepare data for comparison
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
            if 'Accounts_#' in country_data.columns and pd.notna(country_data['Accounts_#'].iloc[0]):
                if country_data['Accounts_#'].iloc[0] > 0:
                    st.metric("Registered Player Accounts", f"{int(country_data['Accounts_#'].iloc[0]):,}")
            
            # Growth rate if available
            if 'GGR CAGR' in country_data.columns and pd.notna(country_data['GGR CAGR'].iloc[0]):
                st.metric("Growth Rate (CAGR)", f"{country_data['GGR CAGR'].iloc[0]}%")
            
            # Additional boolean fields
            boolean_fields = [col for col in ['Offshore?', 'Residents?'] 
                              if col in country_data.columns]
            
            if boolean_fields:
                st.subheader("Additional Information")
                for field in boolean_fields:
                    st.markdown(f"**{field.replace('?', '')}:** {country_data[field].iloc[0]}")
        
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

# Footer
st.markdown("---")
st.markdown("Data source: Research - Summary (Tax worksheet)")
