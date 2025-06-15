# app.py

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta # timedeltaを追加
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
# Yahoo!乗換案内から指定された駅間の情報を取得します。
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
    print(f"DEBUG: Yahoo!乗換案内検索URL: {url}") # DEBUG: 検索URLを出力

    try:
        # ウェブサイトからHTMLを取得 (タイムアウト設定あり)
        response = requests.get(url, timeout=10)
        # HTTPステータスコードが200以外の場合、例外を発生させる
        response.raise_for_status()
        
        # DEBUG: 取得したHTMLの先頭部分を出力して確認
        print(f"DEBUG: 取得したHTMLの先頭部分 (500文字): {response.text[:500]}...") # 文字数を増やしてより多く確認
        
        # BeautifulSoupでHTMLを解析
        soup = BeautifulSoup(response.text, 'html.parser')

        # 最初の検索結果（最も早い到着ルート）を特定
        # HTML構造によりセレクタは異なる可能性があります。
        # 現在のYahoo!乗換案内では、各ルートの概要は 'div.routeSummary' で囲まれています。
        route_summary = soup.find('div', class_='routeSummary')
        
        # DEBUG: route_summaryが見つかったか確認
        if not route_summary:
            print("DEBUG: div.routeSummary が見つかりませんでした。HTML構造が変わった可能性があります。")
            # デバッグのために取得したHTML全体をログに出力することも検討 (大量になるので注意)
            # print(f"DEBUG: Full HTML for inspection:\n{response.text}")

        if route_summary:
            # 出発時刻の抽出
            # 'li.routeDeparture'内の'time.time'タグからテキストを取得
            departure_time_element = route_summary.find('li', class_='routeDeparture')
            departure_time_str = departure_time_element.find('time', class_='time').text.strip() \
                                if departure_time_element and departure_time_element.find('time', class_='time') else '不明'
            print(f"DEBUG: departure_time_element found: {departure_time_element is not None}") # DEBUG
            print(f"DEBUG: departure_time_str: {departure_time_str}") # DEBUG

            # 到着時刻の抽出
            # 'li.routeArrival'内の'time.time'タグからテキストを取得
            arrival_time_element = route_summary.find('li', class_='routeArrival')
            arrival_time_str_raw = arrival_time_element.find('time', class_='time').text.strip() \
                               if arrival_time_element and arrival_time_element.find('time', class_='time') else '不明' # ここを修正
            print(f"DEBUG: arrival_time_element found: {arrival_time_element is not None}") # DEBUG
            print(f"DEBUG: arrival_time_str_raw: {arrival_time_str_raw}") # DEBUG
            
            # 所要時間の抽出 (例: 所要時間 nn分)
            # 'li.routeDuration'内の'em'タグからテキストを取得
            duration_element = route_summary.find('li', class_='routeDuration')
            duration_str = duration_element.find('em').text.strip() \
                           if duration_element and duration_element.find('em') else '不明'
            print(f"DEBUG: duration_element found: {duration_element is not None}") # DEBUG
            print(f"DEBUG: duration_str: {duration_str}") # DEBUG

            # 乗り換え回数の抽出
            # 'li.routeTransfer'内の'em'タグからテキストを取得
            transfer_count_element = route_summary.find('li', class_='routeTransfer')
            transfer_count_str = transfer_count_element.find('em').text.strip() \
                                 if transfer_count_element and transfer_count_element.find('em') else '不明'
            print(f"DEBUG: transfer_count_element found: {transfer_count_element is not None}") # DEBUG
            print(f"DEBUG: transfer_count_str: {transfer_count_str}") # DEBUG

            # 翌日到着の判定と時刻のパース
            arrival_is_next_day = "翌日" in arrival_time_str_raw
            
            # '(翌日)' などの表記を取り除く
            arrival_time_clean = arrival_time_str_raw.replace('(翌日)', '').strip()

            try:
                # 現在の年月日と取得した時分でdatetimeオブジェクトを作成
                # これは到着時刻の計算に使用するため
                current_date = now.date()
                arrival_time_obj = datetime.strptime(arrival_time_clean, '%H:%M').time()
                
                # 到着日の決定
                arrival_datetime = datetime.combine(current_date, arrival_time_obj)
                
                # もし「翌日」と表示されていれば、日付を1日進める
                if arrival_is_next_day:
                    arrival_datetime += timedelta(days=1)
                print(f"DEBUG: Parsed arrival_datetime: {arrival_datetime}") # DEBUG
                
            except ValueError as ve:
                # 時刻のパースに失敗した場合
                print(f"DEBUG: 時刻の解析エラー: {ve}, 試行した時刻文字列: '{arrival_time_clean}'")
                return {"status": "error", "message": "時刻情報の解析に失敗しました。"}

            # 成功した場合は、必要な情報と計算用のdatetimeオブジェクトを辞書で返す
            return {
                "status": "success",
                "departure_time_str": departure_time_str,
                "arrival_time_str": arrival_time_clean, # 計算用にクリーンな文字列
                "arrival_datetime": arrival_datetime,   # 計算用（datetimeオブジェクト）
                "duration_str": duration_str,
                "transfer_count_str": transfer_count_str
            }
        else:
            # 時刻表が見つからない場合
            return {"status": "error", "message": "指定された区間の時刻表が見つかりませんでした。駅名が正しいか、運行状況をご確認ください。"}

    except requests.exceptions.RequestException as e:
        # HTTPリクエスト関連のエラー（ネットワーク、タイムアウトなど）
        print(f"スクレイピングエラー（リクエスト）: {e}")
        return {"status": "error", "message": "電車の時刻表を確認中にエラーが発生しました。しばらくしてからもう一度お試しください。"}
    except Exception as e:
        # その他のエラー（HTML解析失敗など）
        print(f"スクレイピングエラー（解析またはその他）: {e}")
        return {"status": "error", "message": "時刻表の情報を取得できませんでした。サイトの構造が変更されたか、一時的な問題の可能性があります。" }


# 受け取ったメッセージに応答する処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text
    print(f"DEBUG: User message received: '{user_text}'") # DEBUG: ここで受信メッセージを出力

    if user_text == "帰ります":
        # スクレイピング関数を呼び出し、JR茨木駅からJR西宮駅の情報を取得
        train_info_result = get_train_info("JR茨木", "JR西宮")
        
        if train_info_result["status"] == "success":
            # 取得した電車の情報
            departure_time_str = train_info_result["departure_time_str"]
            arrival_time_str = train_info_result["arrival_time_str"] 
            arrival_datetime = train_info_result["arrival_datetime"] # datetimeオブジェクト
            duration_str = train_info_result["duration_str"]
            transfer_count_str = train_info_result["transfer_count_str"]

            # 西宮駅から自宅まで自転車で15分を加算
            estimated_home_arrival_datetime = arrival_datetime + timedelta(minutes=15)
            
            # 自宅到着予定時刻の表示形式を決定
            # 今日の日付と自宅到着予定時刻の日付を比較
            if estimated_home_arrival_datetime.date() > datetime.now().date():
                # 翌日になる場合
                estimated_home_arrival_display = f"翌日 {estimated_home_arrival_datetime.strftime('%H:%M')}"
            else:
                # 同日の場合
                estimated_home_arrival_display = estimated_home_arrival_datetime.strftime('%H:%M')

            # 返信メッセージを整形
            reply_text = (
                f"現在の時刻から最も早いルートです。\n"
                f"🚃出発：JR茨木 {departure_time_str}\n"
                f"🚏到着：JR西宮 {arrival_time_str}\n"
                f"⏰所要時間：{duration_str}\n"
                f"🔄乗り換え：{transfer_count_str}\n"
                f"\n" # 区切り
                f"🚴‍♂️自宅到着予定時刻：{estimated_home_arrival_display}"
            )
            final_reply = f"おかえりなさい！\n{reply_text}"
        else:
            # エラーメッセージを返す
            final_reply = f"おかえりなさい！\n{train_info_result['message']}"
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

