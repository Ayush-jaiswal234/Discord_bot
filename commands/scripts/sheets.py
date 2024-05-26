from __future__ import print_function
from googleapiclient.discovery import build 
from google.oauth2 import service_account

SCOPES = [
'https://www.googleapis.com/auth/spreadsheets',
'https://www.googleapis.com/auth/drive'
]
credentials = service_account.Credentials.from_service_account_file('service_account.json', scopes=SCOPES)
spreadsheet_service = build('sheets', 'v4', credentials=credentials)
drive_service = build('drive', 'v3', credentials=credentials)


def create(title):
    spreadsheet_details = {
    'properties': {
        'title': title
        }
    }
    sheet = spreadsheet_service.spreadsheets().create(body=spreadsheet_details,
                                    fields='spreadsheetId').execute()
    sheetId = sheet.get('spreadsheetId')
    permission1 = {
    'type': 'anyone',
    'role': 'reader',
    }
    drive_service.permissions().create(fileId=sheetId, body=permission1).execute()
    return sheetId

def write_ranges(spreadsheet_id,range_of_sheet,values):
    value_input_option='USER_ENTERED'
    body = {
        'values': values
    }
    result = spreadsheet_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=range_of_sheet,
        valueInputOption=value_input_option, body=body).execute()