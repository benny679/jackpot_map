import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import folium_static

# Load secrets
tax_spreadsheet_id = st.secrets["spreadsheet"]["spreadsheet_id"]
jackpot_spreadsheet_id = st.secrets["jackpot_spreadsheet"]["spreadsheet_id"]
credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"])
client = gspread.authorize(credentials)

# Load Tax Data
tax_sheet = client.open_by_key(tax_spreadsheet_id).worksheet("Tax")
df_tax = pd.DataFrame(tax_sheet.get_all_records())

# Load Jackpot Data
jackpot_sheet = client.open_by_key(jackpot_spreadsheet_id).worksheet("Jackpot Map")
df_jackpot = pd.DataFrame(jackpot_sheet.get_all_records())

# Merge DataFrames on 'Country_region'
df_merged = pd.merge(df_tax, df_jackpot, left_on='Country_region', right_on='Country', how='left')

# Create a map
st.title("Interactive Tax Map")
m = folium.Map(location=[20, 0], zoom_start=2)

# Add country markers
for _, row in df_merged.iterrows():
    country = row["Country_region"]
    tax_info = f"""
    **Market Region:** {row.get("Market_region", "N/A")}  
    **Regulated:** {row.get("Regulated", "N/A")}  
    **Regulation Type:** {row.get("Regulation_type", "N/A")}  
    **Offshore Allowed:** {row.get("Offshore", "N/A")}  
    **Casino Available:** {row.get("Casino", "N/A")}  
    """

    jackpot_info = row.get("Jackpot_Info", "No jackpot data available")

    popup_html = f"""
    <b>{country}</b><br>
    {tax_info}
    <br><b>Jackpot Data:</b><br>
    {jackpot_info}
    """

    # Ensure 'Latitude' and 'Longitude' columns exist and are not null
    if pd.notnull(row.get("Latitude")) and pd.notnull(row.get("Longitude")):
        folium.Marker(
            location=[row["Latitude"], row["Longitude"]],
            popup=folium.Popup(popup_html, max_width=400)
        ).add_to(m)

# Display the map
folium_static(m)
