"""
Vercel serverless function: QBO TransactionListWithSplits JSON -> CSV

Receives raw QBO report JSON via POST, recursively flattens the nested
Rows structure, and returns a CSV with 9 columns:
  Date, Transaction Type, Num, Posting, Name, Memo, Account, Class, Amount
"""

from http.server import BaseHTTPRequestHandler
import json
import csv
import io


def _extract_rows(row_list, results):
    """Recursively walk QBO nested Rows and collect data rows (ColData arrays)."""
    if not row_list:
        return
    for row in row_list:
        if "ColData" in row:
            col_data = row["ColData"]
            if col_data and len(col_data) > 0:
                first_val = col_data[0].get("value", "")
                if first_val and "Total" not in first_val:
                    results.append([c.get("value", "") for c in col_data])
        rows_obj = row.get("Rows")
        if rows_obj and "Row" in rows_obj:
            _extract_rows(rows_obj["Row"], results)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            report = json.loads(body.decode("utf-8"))
        except Exception as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Invalid JSON: {str(e)}"}).encode())
            return

        columns = report.get("Columns", {}).get("Column", [])
        headers = [c.get("ColTitle", "") for c in columns]
        if not headers:
            headers = ["Date", "Transaction Type", "Num", "Posting", "Name",
                        "Memo", "Account", "Class", "Amount"]

        data_rows = []
        top_rows = report.get("Rows", {}).get("Row", [])
        _extract_rows(top_rows, data_rows)

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(headers)
        writer.writerows(data_rows)
        csv_text = buf.getvalue()

        self.send_response(200)
        self.send_header("Content-Type", "text/csv")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(csv_text.encode())
