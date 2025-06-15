from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, re, requests
from bs4 import BeautifulSoup
from urllib.parse import quote

app = Flask(__name__)

# 環境変数からLINEのアクセストークンとチャネルシークレットを取得
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

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
def handle_message(event):
    text = event.message.text.strip()

    if text == "帰ります":
        result = get_train_info("西宮", "大阪")
        if result["status"] == "success":
            reply = f"次の電車：{result['dep']} → {result['arr']}\n路線：{result['line']}"
        else:
            reply = result["message"]
    else:
        reply = "「帰ります」と送ってください"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

def get_train_info(from_st, to_st):
    url = f"https://transit.yahoo.co.jp/search/result?from={quote(from_st)}&to={quote(to_st)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
    except Exception as e:
        return {"status": "error", "message": f"経路検索に失敗しました: {e}"}

    # レスポンスHTMLを保存（Renderではログ代わり）
    try:
        with open("yahoo_result.html", "w", encoding="utf-8") as f:
            f.write(r.text)
    except Exception as e:
        print(f"HTML保存エラー: {e}")

    # 時刻を正規表現で抽出（例: 7:32, 18:45など）
    times = re.findall(r'\d{1,2}:\d{2}', r.text)
    if len(times) < 2:
        return {"status": "error", "message": "時刻解析でエラーが発生しました（時刻が2つ未満）"}

    dep, arr = times[0], times[-1]

    # 路線情報を取得（HTMLパース）
    try:
        soup = BeautifulSoup(r.text, "html.parser")
        line_el = soup.select_one("ol.routeDetail li.transport")
        line_info = line_el.get_text(strip=True) if line_el else "路線情報未取得"
    except Exception:
        line_info = "路線情報取得でエラー"

    return {
        "status": "success",
        "dep": dep,
        "arr": arr,
        "line": line_info
    }

if __name__ == "__main__":
    app.run()
