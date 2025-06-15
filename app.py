# app.py

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import urllib.parse # URLエンコード用

# .envファイルの読み込み
# ローカル環境でのみ使用されます。Renderなどのデプロイ環境では、
# 環境変数を直接設定してください。
load_dotenv()

# 環境変数からLINEの設定を取得
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

# 環境変数が取得できているか確認（デバッグ用）
if not LINE_CHANNEL_ACCESS_TOKEN:
    print("WARNING: LINE_CHANNEL_ACCESS_TOKENが設定されていません。")
if not LINE_CHANNEL_SECRET:
    print("WARNING: LINE_CHANNEL_SECRETが設定されていません。")

# Flaskアプリの作成
app = Flask(__name__)

# LINE Bot APIとWebhookHandlerの初期化
# LINE Bot SDK v3では非推奨と表示されることがありますが、機能には影響ありません。
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# LINEのWebhookを受け取るエンドポイント
@app.route("/callback", methods=["POST"])
def callback():
    # LINEからのリクエストヘッダーにある署名を取得
    signature = request.headers.get("X-Line-Signature")
    # リクエストボディをテキストとして取得
    body = request.get_data(as_text=True)

    try:
        # Webhookハンドラーでリクエストボディと署名を処理
        # 署名が不正な場合はInvalidSignatureErrorが発生
        handler.handle(body, signature)
    except InvalidSignatureError:
        # 署名エラーの場合、HTTP 400 Bad Requestを返す
        abort(400)

    # 正常に処理された場合、HTTP 200 OKを返す
    return "OK", 200

# 電車情報をスクレイピングして取得する関数
# Yahoo!乗換案内からJR西宮駅とJR茨木駅間の情報を取得します。
# 注意: ウェブサイトのHTML構造は変更される可能性があるため、
# その場合、この関数のセレクタを更新する必要があります。
def get_train_info(from_station, to_station):
    # 現在時刻を取得
    now = datetime.now()
    year = now.year
    month = now.month
    day = now.day
    hour = now.hour
    minute = now.minute

    # Yahoo!乗換案内の検索URLを構築
    # 駅名はURLエンコードする必要があります
    from_station_encoded = urllib.parse.quote(from_station)
    to_station_encoded = urllib.parse.quote(to_station)

    # 検索条件: 到着時刻が早い順 (expkind=1)
    url = (
        f"https://transit.yahoo.co.jp/search/result?"
        f"from={from_station_encoded}&to={to_station_encoded}"
        f"&y={year}&m={month}&d={day}"
        f"&hh={hour}&mm={minute}"
        f"&expkind=1" # 到着時刻が早い順
    )

    try:
        # ウェブサイトからHTMLを取得 (タイムアウト設定あり)
        response = requests.get(url, timeout=10)
        # HTTPステータスコードが200以外の場合、例外を発生させる
        response.raise_for_status()
        # BeautifulSoupでHTMLを解析
        soup = BeautifulSoup(response.text, 'html.parser')

        # 最初の検索結果（最も早い到着ルート）を特定
        # HTML構造によりセレクタは異なる可能性があります。
        # 現在のYahoo!乗換案内では、各ルートの概要は 'div.routeSummary' で囲まれています。
        route_summary = soup.find('div', class_='routeSummary')

        if route_summary:
            # 出発時刻の抽出
            # 'li.routeDeparture'内の'time.time'タグからテキストを取得
            departure_time_element = route_summary.find('li', class_='routeDeparture')
            departure_time_str = departure_time_element.find('time', class_='time').text.strip() \
                                if departure_time_element and departure_time_element.find('time', class_='time') else '不明'

            # 到着時刻の抽出
            # 'li.routeArrival'内の'time.time'タグからテキストを取得
            arrival_time_element = route_summary.find('li', class_='routeArrival')
            arrival_time_str = arrival_time_element.find('time', class_='time').text.strip() \
                               if arrival_time_element and arrival_time_element.find('time', class_='time') else '不明'

            # 所要時間の抽出 (例: 所要時間 nn分)
            # 'li.routeDuration'内の'em'タグからテキストを取得
            duration_element = route_summary.find('li', class_='routeDuration')
            duration_str = duration_element.find('em').text.strip() \
                           if duration_element and duration_element.find('em') else '不明'

            # 乗り換え回数の抽出
            # 'li.routeTransfer'内の'em'タグからテキストを取得
            transfer_count_element = route_summary.find('li', class_='routeTransfer')
            transfer_count_str = transfer_count_element.find('em').text.strip() \
                                 if transfer_count_element and transfer_count_element.find('em') else '不明'

            # 結果メッセージを整形して返す
            return (
                f"現在の時刻から最も早いルートです。\n"
                f"🚃出発：{from_station} {departure_time_str}\n"
                f"🚏到着：{to_station} {arrival_time_str}\n"
                f"⏰所要時間：{duration_str}\n"
                f"🔄乗り換え：{transfer_count_str}"
            )
        else:
            # 時刻表が見つからない場合
            return "指定された区間の時刻表が見つかりませんでした。駅名が正しいか、運行状況をご確認ください。"

    except requests.exceptions.RequestException as e:
        # HTTPリクエスト関連のエラー（ネットワーク、タイムアウトなど）
        print(f"スクレイピングエラー（リクエスト）: {e}")
        return "電車の時刻表を確認中にエラーが発生しました。しばらくしてからもう一度お試しください。"
    except Exception as e:
        # その他のエラー（HTML解析失敗など）
        print(f"スクレイピングエラー（解析またはその他）: {e}")
        return "時刻表の情報を取得できませんでした。サイトの構造が変更されたか、一時的な問題の可能性があります。"


# 受け取ったメッセージに応答する処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text

    if user_text == "帰ります":
        # スクレイピング関数を呼び出し、JR西宮駅とJR茨木駅の情報を取得
        reply_text = get_train_info("JR西宮", "JR茨木")
        
        # ユーザーに返信する前に、最初に「おかえりなさい！」のメッセージを付加
        final_reply = f"おかえりなさい！\n{reply_text}"
    else:
        final_reply = f"「{user_text}」ですね！"

    # ユーザーに返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=final_reply)
    )

# Flaskアプリケーションの実行
# ローカルテスト用（Renderなどのデプロイ環境では、GunicornなどのWSGIサーバーが自動で実行します）
if __name__ == "__main__":
    # Renderから提供されるポートを取得。なければデフォルトで5000を使う（一般的）
    port = int(os.environ.get("PORT", 5000))

    # ホストを'0.0.0.0'に設定して、外部からのアクセスを許可する
    app.run(host="0.0.0.0", port=port)
