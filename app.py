import os
import json
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify, send_from_directory
from google.oauth2 import service_account
from googleapiclient.discovery import build


# 建立 Flask app（你原本少了這行）
app = Flask(__name__, static_folder="static")

# 取得目前 app.py 所在資料夾
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Google Sheet 設定
SPREADSHEET_ID = "1rWKe2Ks3f6d5D-iObjAQdrtoEWYVh0edG3LbEd-ZvKk"
RANGE_NAME = "工作表1!A:Z"  # ← 我順便幫你改成穩定寫法

# Service Account 金鑰（用絕對路徑，已修好）
SERVICE_ACCOUNT_FILE = os.path.join(
    BASE_DIR,
    "global-phalanx-468617-s5-9cc155b81aa0.json"
)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
# Google Sheets credentials（Render / local 雙模式）
if os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
    service_account_info = json.loads(
        os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    )
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
else:
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )


service = build("sheets", "v4", credentials=credentials)
sheet = service.spreadsheets()

@app.route("/api/search")
def api_search():
    # 台灣時間 GMT+8
    taipei_tz = timezone(timedelta(hours=8))
    updated_time = datetime.now(taipei_tz).strftime("%Y-%m-%d %H:%M")

    keyword = request.args.get("q", "").strip()
    if not keyword:
        return jsonify({"error": "請輸入查詢關鍵字"}), 400

    try:
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                    range=RANGE_NAME).execute()
        values = result.get("values", [])
        # 去掉標題列
        rows = values[1:] if len(values) > 1 else []

    except Exception as e:
        return jsonify({"error": "資料載入失敗，請稍後再試。", "detail": str(e)}), 500

    not_picked_up = []
    picked_up = []

    for row in rows:
        # 用安全取值避免 IndexError
        def get_val(idx):
            return row[idx].strip() if idx < len(row) else ""

        name = get_val(0)
        phone = get_val(1)
        sender_name = get_val(2)
        tickets = get_val(3)
        number = get_val(4)
        need_pay = get_val(5).upper() == "TRUE"
        amount = get_val(6)
        picked_up_flag = get_val(7).upper() == "TRUE"

        if not (name == keyword or phone.endswith(keyword)):
            continue

        if picked_up_flag and need_pay:
            pickup_status = "已取票並完成付款"
            pay_status = "已完成付款"
            color = "#b8860b"  # 棕色金色
        elif picked_up_flag:
            pickup_status = "已取票"
            pay_status = f"需要付款 ${amount}" if need_pay else "無需付款"
            color = "#b8860b"
        else:
            pickup_status = "尚未取票"
            pay_status = f"需要付款 ${amount}" if need_pay else "無需付款"
            color = "green"

        item = {
            "pickup_status": pickup_status,
            "pay_status": pay_status,
            "number": number,
            "name": name,
            "tickets": tickets,
            "color": color
        }

        if picked_up_flag:
            picked_up.append(item)
        else:
            not_picked_up.append(item)

    results = not_picked_up + picked_up

    if not results:
        return jsonify({"error": "查無資料，請確認輸入是否正確，或至前台確認。"}), 404

    return jsonify({
        "results": results,
        "updated_time": updated_time
    })

@app.route('/')
def index():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
