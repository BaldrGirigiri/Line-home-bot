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
HOME_ADDRESS = "兵庫県西宮市高木西町8-8"  # 実際の住所に応じて変更

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

    # ステップ①：現在地から最寄り駅まで徒歩
    params_walk = {
        "origin": f"{user_lat},{user_lng}",
        "destination": NISHINOMIYA_STATION,
        "mode": "walking",
        "language": "ja",
        "key": GOOGLE_MAPS_API_KEY
    }
    walk_res = requests.get("https://maps.googleapis.com/maps/api/directions/json", params=params_walk).json()

    if walk_res["status"] != "OK" or not walk_res.get("routes"):
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="徒歩ルートの取得に失敗しました。"))
        return

    duration_walk = walk_res["routes"][0]["legs"][0]["duration"]["text"]

    # ステップ②：現在地から西宮駅まで電車（実際は徒歩の代用として処理）
    params_train = {
        "origin": f"{user_lat},{user_lng}",
        "destination": NISHINOMIYA_STATION,
        "mode": "transit",
        "transit_mode": "train",
        "language": "ja",
        "departure_time": "now",
        "key": GOOGLE_MAPS_API_KEY
    }
    train_res = requests.get("https://maps.googleapis.com/maps/api/directions/json", params=params_train).json()

    if train_res["status"] != "OK" or not train_res.get("routes"):
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="電車ルートの取得に失敗しました。"))
        return

    arrival_time = train_res["routes"][0]["legs"][0]["arrival_time"]["text"]
    duration_train = train_res["routes"][0]["legs"][0]["duration"]["text"]

    # ステップ③：西宮駅から自宅まで自転車
    params_bike = {
        "origin": NISHINOMIYA_STATION,
        "destination": HOME_ADDRESS,
        "mode": "bicycling",
        "language": "ja",
        "key": GOOGLE_MAPS_API_KEY
    }
    bike_res = requests.get("https://maps.googleapis.com/maps/api/directions/json", params=params_bike).json()

    if bike_res["status"] != "OK" or not bike_res.get("routes"):
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="西宮駅から自宅までの自転車ルートが見つかりませんでした。"))
        return

    duration_bike = bike_res["routes"][0]["legs"][0]["duration"]["text"]

    message = f"""\U0001F3E0 帰宅ルート情報（3段階）

1️⃣ 現在地 → 西宮駅（徒歩）
　- 所要時間：約{duration_walk}

2️⃣ 西宮駅まで（電車）
　- 所要時間：約{duration_train}
　- 到着予定：{arrival_time}

3️⃣ 西宮駅 → 自宅（自転車）
　- 所要時間：約{duration_bike}

お気をつけてお帰りください！"""

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
