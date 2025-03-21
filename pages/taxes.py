import streamlit as st
from utils.auth import check_password, logout, initialize_session_state
from utils.ip_manager import log_ip_activity
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2 import service_account
import re
import traceback

# 2. PAGE CONFIGURATION
st.set_page_config(
    page_title="Global iGaming Regulation & Tax Map",
    page_icon="🏦",
    layout="wide"
)

# Function to connect to jackpot data - CORRECTED sheet and worksheet names
def connect_to_jackpots(country=None):
    """
    Function to connect to jackpot data and get jackpots for a specific country.
    Specifically searches for the country in Column C of the Jackpot Map worksheet.

    Args:
        country (str, optional): Country to filter jackpots for. Defaults to None.

    Returns:
        pd.DataFrame: DataFrame containing jackpot data with unique Jackpot Groups
    """
    try:
        # Access the Google Sheet directly using the same credentials as the main app
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ],
        )

        # Connect to the spreadsheet - CORRECTED: Sheet is named "Low Vol JPS"
        gc = gspread.authorize(credentials)
        sheet = gc.open("Low Vol JPS")

        # Specifically target the "Jackpot Map" worksheet - CORRECTED: Worksheet is named "Jackpot Map"
        worksheet = sheet.worksheet("Jackpot Map")

        # Get all data
        all_values = worksheet.get_all_values()

        # Get headers (first row)
        headers = all_values[0]

        # Convert to DataFrame
        jackpot_df = pd.DataFrame(all_values[1:], columns=headers)

        # Column C is typically the 3rd column (index 2)
        country_column = headers[2] if len(headers) > 2 else "Country"

        # If a country is specified, filter for it in column C
        if country and not jackpot_df.empty:
            # Filter for rows where Column C (index 2) matches the country
            filtered_jackpots = jackpot_df[jackpot_df[country_column] == country]

            # If no direct match, try with country mappings
            if filtered_jackpots.empty:
                country_to_region = {
                    "United Kingdom": "UK",
                    "Great Britain": "UK",
                    "UK": "UK & Ireland",
                    "Ireland": "UK & Ireland",
                    "Germany": "Germany",
                    "France": "France",
                    "Spain": "Spain",
                    "Italy": "Italy",
                    "United States": "US",
                    "USA": "US",
                    "US": "North America",
                    "Canada": "Canada",
                    # Add more mappings as needed
                }

                # Try alternative names for the country
                for alt_name, region in country_to_region.items():
                    if alt_name.lower() in country.lower() or country.lower() in alt_name.lower():
                        filtered_jackpots = jackpot_df[jackpot_df[country_column] == alt_name]
                        if not filtered_jackpots.empty:
                            break

                        filtered_jackpots = jackpot_df[jackpot_df[country_column] == region]
                        if not filtered_jackpots.empty:
                            break

            # Filter out rows where Jackpot Group is blank or NaN
            if "Jackpot Group" in filtered_jackpots.columns:
                filtered_jackpots = filtered_jackpots[filtered_jackpots["Jackpot Group"].notna() &
                                                     (filtered_jackpots["Jackpot Group"] != "")]

                # Get one row per unique Jackpot Group
                unique_groups = filtered_jackpots.drop_duplicates(subset=["Jackpot Group"])
                return unique_groups

            return filtered_jackpots

        return jackpot_df

    except Exception as e:
        st.error(f"Error connecting to jackpot data: {e}")
        # Print detailed error for debugging
        import traceback
        st.error(traceback.format_exc())
        return pd.DataFrame()  # Return empty DataFrame on error

# Function to count player accounts from Jackpot Map worksheet
def count_player_accounts(country=None):
    """
    Function to count total player accounts from the Jackpot Map worksheet
    for a specific country or region.

    Args:
        country (str, optional): Country to filter accounts for. Defaults to None.

    Returns:
        int: Total player accounts for the country
    """
    try:
        # Access the Google Sheet directly using the same credentials as the main app
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ],
        )

        # Connect to the spreadsheet - Sheet is named "Low Vol JPS"
        gc = gspread.authorize(credentials)
        sheet = gc.open("Low Vol JPS")

        # Specifically target the "Jackpot Map" worksheet
        worksheet = sheet.worksheet("Jackpot Map")

        # Get all data
        all_values = worksheet.get_all_values()

        # Get headers (first row)
        headers = all_values[0]

        # Convert to DataFrame
        jackpot_df = pd.DataFrame(all_values[1:], columns=headers)

        # Find the column names for Region and Accounts
        region_column = None
        accounts_column = None

        for i, header in enumerate(headers):
            if header.lower() == "region" or header.lower() == "country":
                region_column = header
            elif header.lower() == "accounts":
                accounts_column = header

        if not region_column or not accounts_column:
            return 0

        # If country is specified, filter for it in the Region column
        if country and not jackpot_df.empty:
            # Try exact match first
            filtered_jackpots = jackpot_df[jackpot_df[region_column] == country]

            # If no direct match, try with country mappings
            if filtered_jackpots.empty:
                country_to_region = {
                    "United Kingdom": "UK",
                    "Great Britain": "UK",
                    "UK": "UK & Ireland",
                    "Ireland": "UK & Ireland",
                    "Germany": "Germany",
                    "France": "France",
                    "Spain": "Spain",
                    "Italy": "Italy",
                    "United States": "US",
                    "USA": "US",
                    "US": "North America",
                    "Canada": "Canada",
                    # Add more mappings as needed
                }

                # Try alternative names for the country
                for alt_name, region in country_to_region.items():
                    if alt_name.lower() in country.lower() or country.lower() in alt_name.lower():
                        filtered_jackpots = jackpot_df[jackpot_df[region_column] == alt_name]
                        if not filtered_jackpots.empty:
                            break

                        filtered_jackpots = jackpot_df[jackpot_df[region_column] == region]
                        if not filtered_jackpots.empty:
                            break

            # Count total accounts from the filtered results
            if not filtered_jackpots.empty and accounts_column in filtered_jackpots.columns:
                # Sum the Accounts column, handling non-numeric values
                total_accounts = 0
                for account_value in filtered_jackpots[accounts_column]:
                    try:
                        # Try to convert to numeric and add to total
                        if pd.notna(account_value) and account_value != "":
                            total_accounts += int(float(account_value))
                    except (ValueError, TypeError):
                        # Skip non-numeric values
                        pass

                return total_accounts

        return 0

    except Exception as e:
        st.error(f"Error counting player accounts: {e}")
        # Print detailed error for debugging
        import traceback
        st.error(traceback.format_exc())
        return 0  # Return 0 on error

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

        st.info("Connected to Google Sheet. Processing data...")

        # Get all values
        all_values = worksheet.get_all_values()

        if len(all_values) < 3:  # Need at least 2 header rows and 1 data row
            st.error("Not enough rows in the sheet")
            return pd.DataFrame()

        # Get the first row as header and remove any sample data
        header_row = all_values[0]

        # Clean headers - no combining, just use the first row
        cleaned_headers = []
        for header in header_row:
            if header.strip():
                cleaned_headers.append(header.strip())
            else:
                cleaned_headers.append(f"Column_{len(cleaned_headers)}")

        # Ensure headers are unique
        unique_headers = []
        seen = {}
        for h in cleaned_headers:
            if h in seen:
                unique_headers.append(f"{h}_{seen[h]}")
                seen[h] += 1
            else:
                unique_headers.append(h)
                seen[h] = 1

        # Use data starting from row 2 (skip header row)
        data_rows = all_values[1:]

        # Create DataFrame
        df = pd.DataFrame(data_rows, columns=unique_headers)

        # Convert numeric columns
        numeric_cols = ["GGR CAGR", "Operator_tax", "Player_tax", "Accounts_#"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df

    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.error("Please check your Google Sheet permissions and ensure the 'Research - Summary' sheet with 'Tax' worksheet exists.")
        # Raise the exception to see detailed error message during development
        raise e

# 4. INITIALIZE SESSION STATE
initialize_session_state()

# 5. AUTHENTICATION CHECK
if check_password():
    # Log the page view
    if "username" in st.session_state and "ip_address" in st.session_state:
        log_ip_activity(st.session_state["username"], "page_view_igaming_dashboard", st.session_state["ip_address"])
    
    # Show logout button and user info
    st.sidebar.button("Logout", on_click=logout)
    st.sidebar.info(f"Logged in as: {st.session_state['username']} ({st.session_state['user_role']})")
    
    if st.session_state["user_role"] == "admin":
        st.sidebar.info(f"Your IP: {st.session_state['ip_address']}")
    
    # 6. AUTHENTICATED CONTENT - ALL DASHBOARD ELEMENTS
    # Title and description
    st.title("Global iGaming Regulation & Tax Dashboard")
    st.markdown("Interactive map of global iGaming regulations and tax data. Click on countries or filter by region to view detailed information.")

    # Load data
    df = load_data()

    # Sidebar filters
    st.sidebar.header("Filters")

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

        # Safety check for required columns
        if 'Country_region' not in filtered_df.columns:
            st.error("Country_region column not found in dataset")
        elif filtered_df.empty:
            st.warning("No data available with current filters")
        else:
            # Callback for map clicks
            if "clickData" not in st.session_state:
                st.session_state.clickData = None

            # Color coding for regulation status
            if 'Regulated' in filtered_df.columns:
                # Create color map based on unique values
                regulated_values = filtered_df['Regulated'].unique().tolist()
                if len(regulated_values) > 0:
                    # Create appropriate color mapping
                    color_map = {}
                    for val in regulated_values:
                        if isinstance(val, str):
                            lower_val = val.lower()
                            if "yes" in lower_val or "full" in lower_val:
                                color_map[val] = "#2E8B57"  # Green
                            elif "partial" in lower_val or "limited" in lower_val:
                                color_map[val] = "#FFA500"  # Orange
                            elif "no" in lower_val or "not" in lower_val or "illegal" in lower_val:
                                color_map[val] = "#B22222"  # Red
                            else:
                                color_map[val] = "#808080"  # Gray for unknown

                    # Create hover data with only the columns that exist
                    hover_data_cols = []
                    for col in ["Market_region", "Regulation_type", "Offshore?", "Casino", "iGaming", "Betting", "iBetting"]:
                        if col in filtered_df.columns:
                            hover_data_cols.append(col)

                    fig = px.choropleth(
                        filtered_df,
                        locations="Country_region",
                        locationmode="country names",
                        color="Regulated",
                        hover_name="Country_region",
                        hover_data=hover_data_cols,
                        color_discrete_map=color_map,
                        title="iGaming Regulation Status by Country (Click on a country for details)"
                    )

                    fig.update_layout(
                        height=600,
                        margin={"r": 0, "t": 30, "l": 0, "b": 0},
                    )

                    # Display map
                    map_chart = st.plotly_chart(fig, use_container_width=True)

                    # Get click data (only works in Streamlit 1.10.0+)
                    if st.session_state.clickData is not None:
                        click_data = st.session_state.clickData
                        country = click_data['points'][0]['location']
                        st.session_state.selected_country = country
                else:
                    st.warning("No regulation status data available")
            else:
                st.warning("No regulation status column found in the dataset")

            # Alternative method for older Streamlit versions
            st.markdown("""
            <style>
            /* Make the map clickable */
            .js-plotly-plot .plotly .choroplethlayer {
                cursor: pointer;
            }
            </style>
            """, unsafe_allow_html=True)

            st.write("👆 Click on any country to see detailed information")

            # Filter for specific gaming types
            gaming_types = [col for col in ["Casino", "iGaming", "Betting", "iBetting"] if col in filtered_df.columns]
            if gaming_types:
                selected_gaming_type = st.selectbox("View regulation status for specific type:", gaming_types)

                # Create a map for the selected gaming type
                hover_data_cols = []
                for col in ["Market_region", "Regulation_type", selected_gaming_type]:
                    if col in filtered_df.columns:
                        hover_data_cols.append(col)

                fig_gaming = px.choropleth(
                    filtered_df,
                    locations="Country_region",
                    locationmode="country names",
                    color=selected_gaming_type,
                    hover_name="Country_region",
                    hover_data=hover_data_cols,
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

        if tax_options:
            tax_type = st.radio("Select Tax Type:", tax_options,
                              format_func=lambda x: x.replace("_", " ").title())

            # Create hover data list with only columns that exist
            hover_data_cols = []
            for col in ["Market_region", "Regulated", tax_type]:
                if col in filtered_df.columns:
                    hover_data_cols.append(col)

            # Create tax rate map
            fig_tax = px.choropleth(
                filtered_df,
                locations="Country_region",
                locationmode="country names",
                color=tax_type,
                hover_name="Country_region",
                hover_data=hover_data_cols,
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
            hover_data_cols = []
            for col in ["Market_region", "Regulated", "GGR CAGR"]:
                if col in filtered_df.columns:
                    hover_data_cols.append(col)

            st.subheader("Market Growth (CAGR) by Country")

            fig_growth = px.choropleth(
                filtered_df,
                locations="Country_region",
                locationmode="country names",
                color="GGR CAGR",
                hover_name="Country_region",
                hover_data=hover_data_cols,
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

        # Specific Responsible Gambling measures
        rg_measures = [col for col in ['Stake_limit', 'Deposit_limit', 'Withdrawal_limit'] if col in df.columns]

        if rg_measures:
            st.subheader("Responsible Gambling Measures")
            selected_measure = st.selectbox("Select Measure", rg_measures)

            # Create hover data with only existing columns
            hover_data_cols = []
            for col in ["Market_region", selected_measure]:
                if col in filtered_df.columns:
                    hover_data_cols.append(col)

            # Create a map for the selected measure
            fig_measure = px.choropleth(
                filtered_df,
                locations="Country_region",
                locationmode="country names",
                color=selected_measure,
                hover_name="Country_region",
                hover_data=hover_data_cols,
                color_discrete_sequence=px.colors.qualitative.Safe,
                title=f"{selected_measure.replace('_', ' ').title()} Requirements by Country"
            )

            fig_measure.update_layout(
                height=500,
                margin={"r": 0, "t": 30, "l": 0, "b": 0}
            )

            st.plotly_chart(fig_measure, use_container_width=True)

            # Table of RG measures
            st.subheader("Responsible Gambling Measures by Country")

            # Create a list of columns that exist
            table_cols = ['Country_region', 'Market_region'] + rg_measures
            table_cols = [col for col in table_cols if col in filtered_df.columns]

            rg_data = filtered_df[table_cols]
            st.dataframe(rg_data, use_container_width=True)
        else:
            st.info("No responsible gambling measure columns found in the dataset.")

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

        # Define desired default columns based on known columns
        desired_defaults = ["Country_region", "Market_region", "Regulated", "Regulation_type", "Operator_tax", "Player_tax"]

        # Filter to only include columns that actually exist in the DataFrame
        default_columns = [col for col in desired_defaults if col in available_columns]

        # If no default columns exist, don't specify any defaults
        if default_columns:
            selected_columns = st.multiselect(
                "Select columns to display",
                available_columns,
                default=default_columns
            )
        else:
            selected_columns = st.multiselect(
                "Select columns to display",
                available_columns
            )

        # If nothing selected, show all columns
        if not selected_columns:
            selected_columns = available_columns

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

    # Country details section (displayed when a country is clicked)
    st.header("Country Details")

    # Initialize an empty container for country details
    country_details = st.empty()

    # Initialize the selected country from URL parameters or click events
    if "selected_country" not in st.session_state:
        # Check URL parameters first
        params = st.query_params
        if "country" in params:
            st.session_state.selected_country = params["country"]
        else:
            st.session_state.selected_country = None

    # Country selection - either from dropdown or map click
    if 'Country_region' in filtered_df.columns and not filtered_df.empty:
        country_list = sorted(filtered_df['Country_region'].unique())

        # Create a dropdown for manual selection
        selected_country_dropdown = st.selectbox(
            "Select a country or click on the map",
            [""] + country_list,
            index=0
        )

        # Update selected country if dropdown is used
        if selected_country_dropdown:
            st.session_state.selected_country = selected_country_dropdown

    # Display selected country data
    if st.session_state.selected_country:
        country_data = filtered_df[filtered_df['Country_region'] == st.session_state.selected_country]

        if not country_data.empty:
            with country_details.container():
                # Main country info header
                st.subheader(f"{country_data['Country_region'].iloc[0]} - iGaming Regulation & Tax Details")

                # Create tabs for different categories of information
                info_tab1, info_tab2, info_tab3, info_tab4 = st.tabs([
                    "Regulation", "Tax & Market", "Responsible Gambling", "Jackpots"
                ])

                # Regulation tab
                with info_tab1:
                    col1, col2 = st.columns([1, 1])

                    with col1:
                        # Market region
                        if 'Market_region' in country_data.columns:
                            st.info(f"**Market Region:** {country_data['Market_region'].iloc[0]}")

                        # Regulation info
                        if 'Regulated' in country_data.columns:
                            regulated_value = country_data['Regulated'].iloc[0]
                            if pd.notna(regulated_value):
                                if str(regulated_value).lower() in ['yes', 'true', '1']:
                                    st.success(f"**Regulated:** {regulated_value}")
                                elif str(regulated_value).lower() in ['partially', 'limited']:
                                    st.warning(f"**Regulated:** {regulated_value}")
                                else:
                                    st.error(f"**Regulated:** {regulated_value}")

                        # Regulation type
                        if 'Regulation_type' in country_data.columns and pd.notna(country_data['Regulation_type'].iloc[0]):
                            st.write(f"**Regulation Type:** {country_data['Regulation_type'].iloc[0]}")

                    with col2:
                        # Offshore & Residents info with icons
                        col_a, col_b = st.columns(2)

                        with col_a:
                            if 'Offshore?' in country_data.columns:
                                offshore = country_data['Offshore?'].iloc[0]
                                if pd.notna(offshore):
                                    if str(offshore).lower() in ['yes', 'true', '1']:
                                        st.write("**Offshore:** ✅")
                                    else:
                                        st.write("**Offshore:** ❌")

                        with col_b:
                            if 'Residents?' in country_data.columns:
                                residents = country_data['Residents?'].iloc[0]
                                if pd.notna(residents):
                                    if str(residents).lower() in ['yes', 'true', '1']:
                                        st.write("**Residents:** ✅")
                                    else:
                                        st.write("**Residents:** ❌")

                        # Gaming types in a nice format
                        st.subheader("Available Gaming Types")
                        gaming_cols = [
                            ('Casino', 'casino'),
                            ('iGaming', 'video-game'),
                            ('Betting', 'target'),
                            ('iBetting', 'globe')
                        ]

                        for col_name, icon in gaming_cols:
                            if col_name in country_data.columns and pd.notna(country_data[col_name].iloc[0]):
                                value = country_data[col_name].iloc[0]
                                if str(value).lower() in ['regulated', 'yes', 'legal', 'allowed']:
                                    st.success(f"**{col_name}:** {value}")
                                elif str(value).lower() in ['partially', 'limited']:
                                    st.warning(f"**{col_name}:** {value}")
                                elif str(value).lower() in ['no', 'illegal', 'prohibited']:
                                    st.error(f"**{col_name}:** {value}")
                                else:
                                    st.info(f"**{col_name}:** {value}")

                    # Notes in an expander
                    if 'Notes' in country_data.columns and pd.notna(country_data['Notes'].iloc[0]):
                        with st.expander("Additional Notes"):
                            st.write(country_data['Notes'].iloc[0])

                    # Triggering reviews
                    if 'Triggering reviews' in country_data.columns and pd.notna(country_data['Triggering reviews'].iloc[0]):
                        with st.expander("Triggering Reviews"):
                            st.write(country_data['Triggering reviews'].iloc[0])

                # Tax & Market tab
                with info_tab2:
                    col1, col2 = st.columns([1, 1])

                    with col1:
                        # Tax information in metrics
                        st.subheader("Tax Rates")

                        # Display Player Tax only
                        if 'Player_tax' in country_data.columns and pd.notna(country_data['Player_tax'].iloc[0]):
                            player_tax_value = country_data['Player_tax'].iloc[0]
                            st.metric(
                                "Player Tax",
                                f"{player_tax_value}%"
                            )

                            # Add a more detailed explanation of the player tax
                            st.write(f"**Player Tax Details:** The player tax rate for {st.session_state.selected_country} is {player_tax_value}%. This is the tax applied to players on their gambling winnings.")
                        else:
                            st.info("No player tax data available for this country.")

                        # Get player accounts count from Jackpot Map worksheet
                        player_accounts = count_player_accounts(st.session_state.selected_country)

                        # Display the account count
                        if player_accounts > 0:
                            st.metric("Registered Player Accounts", f"{player_accounts:,}")
                        else:
                            # Fallback to the old method if no accounts found in Jackpot Map
                            if 'Accounts_#' in country_data.columns and pd.notna(country_data['Accounts_#'].iloc[0]):
                                try:
                                    accounts = int(float(country_data['Accounts_#'].iloc[0]))
                                    st.metric("Registered Player Accounts", f"{accounts:,}")
                                except (ValueError, TypeError):
                                    st.write(f"**Player Accounts:** {country_data['Accounts_#'].iloc[0]}")
                            else:
                                st.info("No registered player accounts data available for this country.")

                    with col2:
                        # Growth rate if available
                        if 'GGR CAGR' in country_data.columns and pd.notna(country_data['GGR CAGR'].iloc[0]):
                            st.metric(
                                "Growth Rate (CAGR)",
                                f"{country_data['GGR CAGR'].iloc[0]}%",
                                delta=None
                            )

                        # Create a bar chart comparing with regional average for Player Tax only
                        st.subheader("Player Tax Regional Comparison")

                        if 'Player_tax' in country_data.columns and pd.notna(country_data['Player_tax'].iloc[0]) and 'Market_region' in country_data.columns:
                            region = country_data['Market_region'].iloc[0]
                            region_data = filtered_df[filtered_df['Market_region'] == region]

                            if not region_data.empty and 'Player_tax' in region_data.columns:
                                country_val = country_data['Player_tax'].iloc[0]
                                region_avg = region_data['Player_tax'].mean()

                                comparison_data = [{
                                    'Metric': 'Player Tax',
                                    f'{st.session_state.selected_country}': country_val,
                                    f'{region} Average': region_avg
                                }]

                                comparison_df = pd.DataFrame(comparison_data)

                                # Reshape for plotting
                                plot_df = pd.melt(
                                    comparison_df,
                                    id_vars=['Metric'],
                                    value_vars=[f'{st.session_state.selected_country}', f'{region} Average'],
                                    var_name='Entity',
                                    value_name='Tax Rate (%)'
                                )

                                fig = px.bar(
                                    plot_df,
                                    x='Metric',
                                    y='Tax Rate (%)',
                                    color='Entity',
                                    barmode='group',
                                    title=f"Player Tax Comparison with {region} Average"
                                )

                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info(f"No regional comparison data available for {region}.")
                        else:
                            st.info("Regional comparison data not available.")

                # Responsible Gambling tab
                with info_tab3:
                    st.subheader("Responsible Gambling Measures")

                    # RG measures in a nice format
                    col1, col2 = st.columns(2)

                    with col1:
                        # Stake limit
                        if 'Stake_limit' in country_data.columns and pd.notna(country_data['Stake_limit'].iloc[0]):
                            st.write(f"**Stake Limit:** {country_data['Stake_limit'].iloc[0]}")

                        # Deposit limit
                        if 'Deposit_limit' in country_data.columns and pd.notna(country_data['Deposit_limit'].iloc[0]):
                            st.write(f"**Deposit Limit:** {country_data['Deposit_limit'].iloc[0]}")

                    with col2:
                        # Withdrawal limit
                        if 'Withdrawal_limit' in country_data.columns and pd.notna(country_data['Withdrawal_limit'].iloc[0]):
                            st.write(f"**Withdrawal Limit:** {country_data['Withdrawal_limit'].iloc[0]}")

                        # Priority region
                        if 'Priority region' in country_data.columns and pd.notna(country_data['Priority region'].iloc[0]):
                            priority = country_data['Priority region'].iloc[0]
                            if str(priority).lower() in ['yes', 'true', '1']:
                                st.write("**Priority Region:** ✅")
                            else:
                                st.write("**Priority Region:** ❌")

                # Jackpots tab - modified to not return results if jackpot name is blank
                with info_tab4:
                    st.subheader(f"Available Jackpots in {st.session_state.selected_country}")

                    # Connect to jackpot data - search Column C in the Jackpot Map worksheet of the Low Vol JPS sheet
                    jackpot_data = connect_to_jackpots(st.session_state.selected_country)

                    if not jackpot_data.empty:
                        # Make sure jackpot groups are not blank
                        if "Jackpot Group" in jackpot_data.columns and jackpot_data["Jackpot Group"].notna().any() and (jackpot_data["Jackpot Group"] != "").any():
                            # Display jackpot count
                            total_jackpots = len(jackpot_data)
                            unique_groups = jackpot_data["Jackpot Group"].nunique()

                            st.success(f"Found {unique_groups} unique Jackpot Groups available in {st.session_state.selected_country}")

                            # Create columns for metrics
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Unique Jackpot Groups", unique_groups)

                            with col2:
                                if "Provider" in jackpot_data.columns:
                                    unique_providers = jackpot_data["Provider"].nunique()
                                    st.metric("Unique Providers", unique_providers)

                            with col3:
                                st.metric("Total Jackpot Entries", total_jackpots)

                            # Create section for Jackpot Groups
                            st.subheader("Jackpot Groups")

                            # Determine columns to display
                            display_columns = []

                            # Check for important jackpot columns and add them if they exist
                            for col in ["Operator", "Game Name", "Provider", "Type", "Tiers", "Jackpot Group", "Accounts"]:
                                if col in jackpot_data.columns:
                                    display_columns.append(col)

                            # Display the unique jackpot group data
                            st.dataframe(jackpot_data[display_columns], use_container_width=True)

                            # Create a pie chart of Jackpot Groups
                            if len(jackpot_data["Jackpot Group"].unique()) > 1:
                                group_counts = jackpot_data["Jackpot Group"].value_counts().reset_index()
                                group_counts.columns = ["Jackpot Group", "Count"]

                                fig = px.pie(
                                    group_counts,
                                    values="Count",
                                    names="Jackpot Group",
                                    title=f"Jackpot Group Distribution in {st.session_state.selected_country}"
                                )
                                st.plotly_chart(fig, use_container_width=True)
                        else:
                            # No valid jackpot groups found
                            st.info(f"No jackpot data available for {st.session_state.selected_country}.")
                    else:
                        # Empty jackpot data
                        st.info(f"No jackpot data available for {st.session_state.selected_country}.")

    # Footer
    st.markdown("---")
    st.markdown("Data source: Research - Summary (Tax worksheet)")
else:
    # Display message for unauthenticated users
    st.warning("Please log in to access the iGaming Regulation & Tax Dashboard.")
    st.info("This dashboard contains sensitive market information and requires authentication.")
