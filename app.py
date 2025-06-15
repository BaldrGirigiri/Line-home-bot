# app.py

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import urllib.parse
import re

# --- 環境変数読み込み ---
load_dotenv()
CHANNEL_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

app = Flask(__name__)
line_bot_api = LineBotApi(CHANNEL_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

HEADERS = {"User-Agent": "Mozilla/5.0"}

def normalize_station_name(name):
    name = name.strip()
    name = re.sub(r'\s+', '', name)
    name = name.replace('　', '').replace('駅', '')
    return name

def get_train_info(from_st, to_st):
    from_s = normalize_station_name(from_st)
    to_s = normalize_station_name(to_st)
    dep_enc = urllib.parse.quote(from_s)
    arr_enc = urllib.parse.quote(to_s)

    now = datetime.now()
    dt = now
    url = (f"https://transit.yahoo.co.jp/search/result?"
           f"from={dep_enc}&to={arr_enc}"
           f"&y={dt.year}&m={dt.month}&d={dt.day}"
           f"&hh={dt.hour}&mm={dt.minute}&type=1&ticket=ic")

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
    except Exception as ex:
        return {"status": "error", "message": "経路検索に失敗しました。"}

    soup = BeautifulSoup(r.text, "html.parser")
    route = soup.select_one("div.routeSummary")
    if not route:
        return {"status": "error", "message": "経路情報が見つかりません。"}

    try:
        # より安定したセレクタに変更
        dtimes = route.select("ul.time li time")
        if not dtimes or len(dtimes) < 2:
            raise ValueError("時刻が2つ以上見つかりません")

        dep = dtimes[0].get_text(strip=True)
        arr = dtimes[-1].get_text(strip=True)

        info_li = soup.select_one("ol.routeDetail li.transport")
        line_info = info_li.get_text(strip=True) if info_li else "経路情報なし"

        return {"status": "success", "dep": dep, "arr": arr, "line": line_info}

    except Exception as ex:
        print("時刻抽出エラー:", ex)
        return {"status": "error", "message": "時刻解析でエラーが発生しました。"}

@app.route("/callback", methods=["POST"])
def callback():
    sig = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, sig)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    text = event.message.text.strip()
    if "帰ります" in text:
        res = get_train_info("茨木", "西宮")
        if res["status"] == "success":
            arr_dt = datetime.now()
            fmt_arr = res["arr"]
            home_arr = (arr_dt.replace(hour=int(fmt_arr[:2]), minute=int(fmt_arr[3:5]))
                        + timedelta(minutes=15)).strftime("%H:%M")
            reply = (f"🚃 出発予定：{res['dep']}\n"
                     f"🏁 到着予定：{res['arr']}\n"
                     f"📍 経路：{res['line']}\n"
                     f"🚴‍♂️ 自宅到着見込み：{home_arr}")
        else:
            reply = "おかえりなさい！\n" + res.get("message", "エラーが発生しました。")
    else:
        reply = "「帰ります」と送ってください。"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
