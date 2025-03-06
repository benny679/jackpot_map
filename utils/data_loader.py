import pandas as pd
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os

# Use secrets or environment variables for sensitive information
SLACK_TOKEN = os.environ.get('SLACK_TOKEN')
CHANNEL_ID = os.environ.get('SLACK_CHANNEL_ID')

def upload_to_slack(file_path, message):
    """Upload a file to Slack and post a message about the upload using v2 API."""
    if not SLACK_TOKEN:
        st.warning("No Slack token provided. Set the SLACK_TOKEN environment variable.")
        return False

    client = WebClient(token=SLACK_TOKEN)
    try:
        response = client.files_upload_v2(channels=CHANNEL_ID, file=file_path)
        if response["ok"]:
            client.chat_postMessage(channel=CHANNEL_ID, text=message)
            st.success(f"File '{file_path}' uploaded and message posted successfully to Slack.")
            return True
        else:
            st.error(f"Failed to upload file: {response['error']}")
            return False
    except SlackApiError as e:
        st.error(f"Slack API Error: {str(e)}")
        return False

@st.cache_data(ttl=3600)  # Cache data for 1 hour
def load_sheet_data():
    """Load data from Google Sheets."""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Low Vol JPS").worksheet("Jackpot Map")
        data = sheet.get_all_values()
        headers = data.pop(0)
        df = pd.DataFrame(data, columns=headers)

        # Convert appropriate columns to numeric
        numeric_cols = df.columns[df.columns.str.contains('Amount|Level|Value|%|ID', case=False)]
        for col in numeric_cols:
            try:
                df[col] = pd.to_numeric(df[col])
            except (ValueError, TypeError):
                # Keep the column as is if conversion fails
                pass

        return df
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()
