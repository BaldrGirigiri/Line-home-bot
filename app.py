from flask import Flask, request, abort
import requests
import os

# linebot ライブラリの読み込み（Render上で有効、ローカルではダミー定義）
try:
    from linebot import LineBotApi, WebhookHandler
    from linebot.exceptions import InvalidSignatureError
    from linebot.models import MessageEvent, TextMessage, TextSendMessage, LocationMessage
except ModuleNotFoundError:
    print("[警告] linebot ライブラリが見つかりません。ローカルでのテストには注意してください。")
    class Dummy:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    LineBotApi = WebhookHandler = Dummy
    InvalidSignatureError = Exception
    MessageEvent = TextMessage = TextSendMessage = LocationMessage = object

app = Flask(__name__)

# 環境変数から読み込み（Render のダッシュボードで設定）
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "test_token")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "test_secret")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "test_api_key")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 自宅情報
HOME_ADDRESS = "兵庫県西宮市高木西町8-8"  # 必要に応じて変更
STATION_LAT = 34.736082   # 西宮駅の緯度
STATION_LNG = 135.341650  # 西宮駅の経度

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
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

    # ステップ①：現在地→西宮駅（徒歩）
    params_walk = {
        "origin": f"{user_lat},{user_lng}",
        "destination": f"{STATION_LAT},{STATION_LNG}",
        "mode": "walking",
        "language": "ja",
        "key": GOOGLE_MAPS_API_KEY
    }
    walk_res = requests.get("https://maps.googleapis.com/maps/api/directions/json", params=params_walk).json()

    if walk_res.get("status") != "OK" or not walk_res.get("routes"):
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="徒歩ルートの取得に失敗しました。"))
        return

    duration_walk = walk_res["routes"][0]["legs"][0]["duration"]["text"]

    # ステップ②：現在地→西宮駅（電車）
    params_train = {
        "origin": f"{user_lat},{user_lng}",
        "destination": f"{STATION_LAT},{STATION_LNG}",
        "mode": "transit",
        "transit_mode": "train",
        "language": "ja",
        "departure_time": "now",
        "key": GOOGLE_MAPS_API_KEY
    }
    train_res = requests.get("https://maps.googleapis.com/maps/api/directions/json", params=params_train).json()

    if train_res.get("status") != "OK" or not train_res.get("routes"):
        error_status = train_res.get("status", "不明")
        error_message = train_res.get("error_message", "")
        debug_info = f"[デバッグ情報]\nstatus: {error_status}\nmessage: {error_message}"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"電車ルートの取得に失敗しました。\n{debug_info}")
        )
        print("Google Maps Transit API エラー:", train_res)
        return

    leg_train = train_res["routes"][0]["legs"][0]
    arrival_time = leg_train.get("arrival_time", {}).get("text", "不明")
    duration_train = leg_train["duration"]["text"]

    # ステップ③：西宮駅→自宅（自転車）
    params_bike = {
        "origin": f"{STATION_LAT},{STATION_LNG}",
        "destination": HOME_ADDRESS,
        "mode": "bicycling",
        "language": "ja",
        "key": GOOGLE_MAPS_API_KEY
    }
    bike_res = requests.get("https://maps.googleapis.com/maps/api/directions/json", params=params_bike).json()

    if bike_res.get("status") != "OK" or not bike_res.get("routes"):
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="西宮駅から自宅までの自転車ルートが見つかりませんでした。"))
        return

    duration_bike = bike_res["routes"][0]["legs"][0]["duration"]["text"]

    # 結果をまとめて返信
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
