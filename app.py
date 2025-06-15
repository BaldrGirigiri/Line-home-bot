# app.py

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv
import os

# .envファイルの読み込み
load_dotenv()

# 環境変数からLINEの設定を取得
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("071ZBMrKL5U+H4Mw5uOFLxv1JzHfeqB0mjjNF4n5Wc9EgFS6txTljqJOKdYyxoqf/xsIYTfdxMSmuE3OBXWOfwXUwbtbC/oNa+OlyZsBJybzDqGAOIb034WEF805vesvtOhAItwPyPIGnsSTFi1jGgdB04t89/1O/w1cDnyilFU=")
LINE_CHANNEL_SECRET = os.getenv("44472bc7a7dc0b206b77cd2b8dac7e0b")

# Flaskアプリの作成
app = Flask(__name__)
line_bot_api = LineBotApi(071ZBMrKL5U+H4Mw5uOFLxv1JzHfeqB0mjjNF4n5Wc9EgFS6txTljqJOKdYyxoqf/xsIYTfdxMSmuE3OBXWOfwXUwbtbC/oNa+OlyZsBJybzDqGAOIb034WEF805vesvtOhAItwPyPIGnsSTFi1jGgdB04t89/1O/w1cDnyilFU=)
handler = WebhookHandler(44472bc7a7dc0b206b77cd2b8dac7e0b)

# LINEのWebhookを受け取る部分
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK",200

# 受け取ったメッセージに応答する処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text

    if user_text == "帰ります":
        reply_text = "おかえりなさい！電車の時刻を確認しますね🚃"
    else:
        reply_text = f"「{user_text}」ですね！"

    # ユーザーに返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

# ローカルテスト用（Renderでは使わない）
if __name__ == "__main__":
    app.run(port=3000)
