"""
Vercel serverless function: QBO TransactionListWithSplits JSON -> CSV

Receives raw QBO report JSON via POST, recursively flattens the nested
Rows structure, and returns a CSV with 9 columns:
  Date, Transaction Type, Num, Posting, Name, Memo, Account, Class, Amount
"""

import json
import csv
import io


def _extract_rows(row_list, results):
    """Recursively walk QBO nested Rows and collect data rows (ColData arrays)."""
    if not row_list:
        return
    for row in row_list:
        # Data rows have ColData with actual transaction values
        if "ColData" in row:
            col_data = row["ColData"]
            if col_data and len(col_data) > 0:
                first_val = col_data[0].get("value", "")
                # Skip summary/total rows
                if first_val and "Total" not in first_val:
                    results.append([c.get("value", "") for c in col_data])
        # Section rows have nested Rows.Row — recurse into them
        rows_obj = row.get("Rows")
        if rows_obj and "Row" in rows_obj:
            _extract_rows(rows_obj["Row"], results)


def handler(request):
    """Vercel Python serverless handler."""
    if request.method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
            "body": "",
        }

    if request.method != "POST":
        return {
            "statusCode": 405,
            "body": json.dumps({"error": "POST only"}),
        }

    try:
        body = request.body
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        report = json.loads(body)
    except Exception as e:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Invalid JSON: {str(e)}"}),
        }

    # Extract column headers from report metadata
    columns = report.get("Columns", {}).get("Column", [])
    headers = [c.get("ColTitle", "") for c in columns]
    if not headers:
        headers = ["Date", "Transaction Type", "Num", "Posting", "Name",
                    "Memo", "Account", "Class", "Amount"]

    # Recursively extract all data rows
    data_rows = []
    top_rows = report.get("Rows", {}).get("Row", [])
    _extract_rows(top_rows, data_rows)

    # Build CSV
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(data_rows)
    csv_text = buf.getvalue()

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/csv",
            "Access-Control-Allow-Origin": "*",
        },
        "body": csv_text,
    }
