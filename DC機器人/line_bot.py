from flask import Flask, request
from linebot import LineBotApi
from linebot.v3.webhook import WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# 替換為您的 LINE Channel Access Token 和 Channel Secret
LINE_CHANNEL_ACCESS_TOKEN = "2raD8uPEnsSm3qlBWvz0qUuEz7e_7XABkoaAmMeZA5pyFfSjv"
LINE_CHANNEL_SECRET = "95a2e8a531fa15dc5bd6eff7ed8c4d00"

BASE_URL = "https://acgsecrets.hk/bangumi/"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Flask 應用程式
app = Flask(__name__)

# 動畫數據抓取函數
def fetch_bangumi_data(year_month):
    url = f"{BASE_URL}{year_month}/"
    response = requests.get(url)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')

    data_list = []
    items = soup.select("div.acgs-anime-block")
    for item in items:
        title = item.select_one("div.entity_localized_name").text.strip() if item.select_one("div.entity_localized_name") else "未提供名稱"
        broadcast_date = item.select_one("div.anime_onair div.time_today.main_time").text.strip() if item.select_one("div.anime_onair div.time_today.main_time") else "未提供播放日"
        synopsis = item.select_one("div.anime_story").text.strip() if item.select_one("div.anime_story") else "未提供故事大綱。"
        image_tag = item.select_one("div.anime_cover_image img")
        image_url = image_tag["src"] if image_tag else "https://via.placeholder.com/300x400?text=No+Image"
        data_list.append({
            "title": title,
            "broadcast_date": broadcast_date,
            "synopsis": synopsis,
            "image_url": image_url
        })
    return data_list

# 生成回應訊息
def generate_flex_message(anime):
    bubble = BubbleContainer(
        hero={
            "type": "image",
            "url": anime["image_url"],
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover"
        },
        body={
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": anime["title"],
                    "weight": "bold",
                    "size": "lg",
                    "wrap": True
                },
                {
                    "type": "text",
                    "text": f"播放日: {anime['broadcast_date']}",
                    "size": "sm",
                    "color": "#AAAAAA",
                    "wrap": True
                },
                {
                    "type": "text",
                    "text": anime["synopsis"],
                    "size": "sm",
                    "wrap": True
                }
            ]
        }
    )
    return FlexSendMessage(alt_text=anime["title"], contents=bubble)

# LINE Webhook 路由
@app.route("/callback", methods=['POST'])
def callback():
    # 獲取 X-Line-Signature 標頭
    signature = request.headers['X-Line-Signature']

    # 獲取 Webhook 請求的主體內容
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400

    return 'OK', 200

# 處理文字訊息事件
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text

    if user_message.startswith("!anime "):
        year_month = user_message.split(" ")[1]
        if not year_month.isdigit() or len(year_month) != 6:
            reply_message = "請輸入正確的年份和月份格式，例如：`!anime 202501`"
        else:
            try:
                anime_data = fetch_bangumi_data(year_month)
                if anime_data:
                    messages = [generate_flex_message(anime) for anime in anime_data[:5]]  # 僅顯示前 5 部動畫
                    line_bot_api.reply_message(event.reply_token, messages)
                else:
                    reply_message = "未能找到任何動畫數據，請確認輸入的年份和月份是否正確！"
            except Exception as e:
                reply_message = f"發生錯誤：{e}"
    else:
        reply_message = "抱歉，我無法理解您的訊息。請使用 `!anime 年月` 格式查詢動畫。"

    if reply_message:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_message))

# 啟動 Flask 應用
if __name__ == "__main__":
    app.run(port=8000)
