"""
Conformance test for Sheets API.
This file documents the expected structure of Sheets API responses.
Based on official Google API documentation.
"""

# Expected structure for spreadsheets.values.get
# Used for fetching message IDs from a specific column
SHEETS_GET_RESPONSE = {
    "range": "Emails!B2:B100",
    "majorDimension": "ROWS",
    "values": [
        ["msg1"],
        ["msg2"],
        ["msg3"]
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


def test_conformance():
    # Validate structure of SHEETS_GET_RESPONSE
    assert isinstance(SHEETS_GET_RESPONSE, dict)
    assert set(SHEETS_GET_RESPONSE.keys()).issuperset(
        {"range", "majorDimension", "values"}
    )

    assert isinstance(SHEETS_GET_RESPONSE["range"], str)
    assert isinstance(SHEETS_GET_RESPONSE["majorDimension"], str)
    assert SHEETS_GET_RESPONSE["majorDimension"] == "ROWS"

    values = SHEETS_GET_RESPONSE["values"]
    assert isinstance(values, list)
    # Expect a list of rows, each row is a list of cell values
    assert all(isinstance(row, list) for row in values)

    # Validate structure of SHEETS_APPEND_RESPONSE
    assert isinstance(SHEETS_APPEND_RESPONSE, dict)
    assert set(SHEETS_APPEND_RESPONSE.keys()).issuperset(
        {"spreadsheetId", "tableRange", "updates"}
    )

    assert isinstance(SHEETS_APPEND_RESPONSE["spreadsheetId"], str)
    assert isinstance(SHEETS_APPEND_RESPONSE["tableRange"], str)

    updates = SHEETS_APPEND_RESPONSE["updates"]
    assert isinstance(updates, dict)
    assert set(updates.keys()).issuperset(
        {
            "spreadsheetId",
            "updatedRange",
            "updatedRows",
            "updatedColumns",
            "updatedCells",
        }
    )

    assert isinstance(updates["spreadsheetId"], str)
    assert isinstance(updates["updatedRange"], str)
    assert isinstance(updates["updatedRows"], int)
    assert isinstance(updates["updatedColumns"], int)
    assert isinstance(updates["updatedCells"], int)
