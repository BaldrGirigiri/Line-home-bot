from flask import Flask, request, abort
import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# Flaskアプリの初期化
app = Flask(__name__)

# 環境変数からLINEチャネルの情報を取得（Renderで設定）
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

# LINE APIの初期化
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# LINEのWebhook受信エンドポイント
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

# メッセージ受信時の処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text

    if "帰ります" in text:
        # 駅名を適宜変更してください
        from_station = "茨木"
        to_station = "大阪"
        result = get_train_info(from_station, to_station)

        if result["status"] == "success":
            reply = f"出発: {result['dep']}\n到着: {result['arr']}\n路線: {result['line']}"
        else:
            reply = result["message"]
    else:
        reply = "「帰ります」と送ると乗換案内を返信します。"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

# Yahoo乗換案内から時刻を抽出する関数
def get_train_info(from_st, to_st):
    url = f"https://transit.yahoo.co.jp/search/result?from={quote(from_st)}&to={quote(to_st)}"

    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        return {"status": "error", "message": f"経路検索に失敗しました: {e}"}

    soup = BeautifulSoup(r.text, "html.parser")
    all_text = soup.get_text()

    times = re.findall(r'\b\d{1,2}:\d{2}\b', all_text)
    if len(times) < 2:
        return {"status": "error", "message": "時刻解析でエラーが発生しました（時刻が2つ未満）"}

    dep = times[0]
    arr = times[-1]

    line_info = ""
    try:
        line_el = soup.select_one("ol.routeDetail li.transport")
        if line_el:
            line_info = line_el.get_text(strip=True)
    except Exception:
        pass

    return {
        "status": "success",
        "dep": dep,
        "arr": arr,
        "line": line_info or "路線情報未取得"
    }

# Renderで実行するためのエントリーポイント
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
