"""
Conformance test for Sheets API.
This file documents the expected structure of Sheets API responses.
Based on official Google API documentation.
"""

# Expected structure for spreadsheets.values.get
# Used for fetching message IDs from a specific column
SHEETS_GET_RESPONSE = {
    "range": "Emails!B2:B100",
    "majorDimension": "COLUMNS",
    "values": [
        ["msg1", "msg2", "msg3"]
    ]
}

# Expected structure for spreadsheets.values.append
SHEETS_APPEND_RESPONSE = {
    "spreadsheetId": "sheet_123",
    "tableRange": "Emails!A1:G10",
    "updates": {
        "spreadsheetId": "sheet_123",
        "updatedRange": "Emails!A11:G11",
        "updatedRows": 1,
        "updatedColumns": 7,
        "updatedCells": 7
    }
}

def test_placeholder():
    pass
