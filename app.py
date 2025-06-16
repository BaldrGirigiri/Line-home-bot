from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, LocationMessage
import requests
import os

app = Flask(__name__)

# 環境変数から読み込む（Renderにデプロイする場合はダッシュボードで設定）
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 自宅情報
NISHINOMIYA_STATION = "西宮駅"
HOME_ADDRESS = "兵庫県西宮市高木西町8-8"  # 必要に応じて実際の住所に変更

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    if event.message.text == "帰ります":
        reply = "現在地を送ってください（位置情報を共有してください）"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

@handler.add(MessageEvent, message=LocationMessage)
def handle_location(event):
    user_lat = event.message.latitude
    user_lng = event.message.longitude

    # ステップ①：現在地から西宮駅まで電車でのルート検索
    train_url = "https://maps.googleapis.com/maps/api/directions/json"
    params_train = {
        "origin": f"{user_lat},{user_lng}",
        "destination": NISHINOMIYA_STATION,
        "mode": "transit",
        "transit_mode": "train",
        "language": "ja",
        "key": GOOGLE_MAPS_API_KEY
    }
    train_res = requests.get(train_url, params=params_train).json()

    if train_res["status"] != "OK" or not train_res.get("routes"):
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="電車ルートの取得に失敗しました。"))
        return

    arrival_time = train_res["routes"][0]["legs"][0]["arrival_time"]["text"]
    summary_train = train_res["routes"][0]["legs"][0]["steps"]

    # ステップ②：西宮駅から自宅まで自転車
    params_bike = {
        "origin": NISHINOMIYA_STATION,
        "destination": HOME_ADDRESS,
        "mode": "bicycling",
        "language": "ja",
        "key": GOOGLE_MAPS_API_KEY
    }
    bike_res = requests.get(train_url, params=params_bike).json()

    if bike_res["status"] != "OK" or not bike_res.get("routes"):
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="西宮駅から自宅までのルートが見つかりませんでした。"))
        return

    duration_bike = bike_res["routes"][0]["legs"][0]["duration"]["text"]

    message = f"""🏡 帰宅ルート情報

1️⃣ 現在地 → 西宮駅（電車）
　- 到着予定時刻：{arrival_time}

2️⃣ 西宮駅 → 自宅（自転車）
　- 所要時間：約{duration_bike}

お気をつけてお帰りください！"""

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))
