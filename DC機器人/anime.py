import asyncio
import csv
import os
import requests
from bs4 import BeautifulSoup
import discord
from discord.ext import commands
from datetime import datetime
import json

# 設定 Discord Bot Token 和基礎 URL
DISCORD_BOT_TOKEN = "MTMyNjQ2MDk5MDM3MTQwMTc1MA.G_4Ro0.avCCvot-Zm5Cl2ESFKqZ7eShw_5ReM9s-Owm8I"
BASE_URL = "https://acgsecrets.hk/bangumi/"

# 持久化存儲路徑
DATA_FILE = "anime_data.json"

# 建立 Bot 實例
intents = discord.Intents.default()
intents.message_content = True  # 啟用讀取消息內容的 Intent
bot = commands.Bot(command_prefix="!", intents=intents)

# 全局變量儲存動畫數據
server_data = {}
reaction_cooldown = {}
message_data = {}  # 儲存每個消息的分頁狀態和數據

# 抓取動畫數據
def fetch_bangumi_data(url_suffix):
    url = f"{BASE_URL}{url_suffix}/"
    response = requests.get(url)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')

    data_list = []
    items = soup.select("div.acgs-anime-block")
    for item in items:
        title = item.select_one("div.entity_localized_name").text.strip() if item.select_one("div.entity_localized_name") else "未提供名稱"
        broadcast_date = item.select_one("div.anime_onair div.time_today.main_time").text.strip() if item.select_one("div.anime_onair div.time_today.main_time") else "未提供播放日"
        
        # 提取海外播放時間
        overseas_broadcast = item.select("div.anime_streams div.stream-area")
        overseas_broadcast_time = []
        
        for stream in overseas_broadcast:
            region = stream.text.strip()
            platform = stream.find_next("div", class_="steam-site-name").text.strip() if stream.find_next("div", class_="steam-site-name") else "未提供平台"
            time = stream.find_next("span", class_="oa-time").text.strip() if stream.find_next("span", class_="oa-time") else "未提供時間"
            overseas_broadcast_time.append(f"{region}: {platform}, {time}")
        
        # 保證巴哈姆特的信息仍然在海外播放時間中
        bahamut_stream = item.select_one("div.stream-site-item a[title='巴哈姆特動畫瘋']")
        if bahamut_stream:
            bahamut_time = bahamut_stream.find_next("span", class_="oa-time").text.strip() if bahamut_stream.find_next("span", class_="oa-time") else "未提供時間"
            overseas_broadcast_time.append(f"巴哈姆特動畫瘋: {bahamut_time}")
        
        overseas_broadcast_time = "\n".join(overseas_broadcast_time) if overseas_broadcast_time else "未提供海外播放時間"

        # 提取配音員
        voice_actors = ", ".join([f"{cast.select_one('span.type').text.strip()}: {cast.select_one('span.entities').text.strip()}" for cast in item.select("div.anime_cast div.anime_person")]) if item.select("div.anime_cast div.anime_person") else "未提供配音員信息。"
        
        # 提取製作人
        producers = ", ".join([f"{staff.select_one('span.type').text.strip()}: {staff.select_one('span.entities').text.strip()}" for staff in item.select("div.anime_staff div.anime_person")]) if item.select("div.anime_staff div.anime_person") else "未提供製作人信息。"
        
        # 如果製作人與配音員信息重複，去除製作人信息
        if producers in voice_actors:
            producers = "未提供製作人信息。"
        
        image_tag = item.select_one("div.anime_cover_image img")
        image_url = image_tag["src"] if image_tag else "https://via.placeholder.com/300x400?text=No+Image"

        # 修改：抓取正確的故事大綱
        synopsis_tag = item.select_one("div.anime_story")  # 更改為 anime_story
        synopsis = synopsis_tag.text.strip() if synopsis_tag else "未提供故事大綱。"
        
        official_site_tag = item.select_one("div.anime_hashicons a")
        official_site = official_site_tag["href"] if official_site_tag else "N/A"

        data_list.append({
            "title": title,
            "image_url": image_url,
            "broadcast_date": broadcast_date,
            "synopsis": synopsis,
            "official_site": official_site,
            "voice_actors": voice_actors,
            "producers": producers,
            "overseas_broadcast_time": overseas_broadcast_time,  # 海外播放時間，包括平台和時間
        })
    return data_list

# 生成 CSV 文件，只包含動畫名稱
def save_to_csv(data, file_name="anime_titles.csv"):
    rows = [[anime["title"]] for anime in data]

    # 添加表頭
    header = ["動畫名稱"]
    rows.insert(0, header)

    # 寫入 CSV
    with open(file_name, "w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(rows)

    return file_name

# 清理過期的冷卻時間
def clean_reaction_cooldown():
    global reaction_cooldown
    now = asyncio.get_event_loop().time()
    reaction_cooldown = {
        msg_id: {
            user_id: timestamp
            for user_id, timestamp in users.items()
            if now - timestamp < 10  # 保留10秒內的用戶反應
        }
        for msg_id, users in reaction_cooldown.items()
    }

# 更新嵌入消息的顯示部分
def generate_embed(data, page):
    anime = data[page]
    embed = discord.Embed(
        title=f"{anime['title']} (第 {page + 1}/{len(data)} 部動畫)",
        url=anime['official_site'] if anime['official_site'].startswith("http") else None,
        color=discord.Color.blue(),
    )
    embed.set_image(url=anime["image_url"])
    embed.add_field(name="播放日", value=anime["broadcast_date"], inline=False)
    embed.add_field(name="海外播放時間", value=anime["overseas_broadcast_time"], inline=False)  # 海外播放時間
    embed.add_field(name="故事大綱", value=anime["synopsis"][:500], inline=False)
    embed.add_field(name="配音員", value=anime["voice_actors"], inline=False)
    embed.add_field(name="製作人", value=anime["producers"], inline=False)
    return embed

@bot.event
async def on_reaction_add(reaction, user):
    global reaction_cooldown, message_data

    if user == bot.user:
        return

@bot.command()
async def anime(ctx, year_month: str):
    global server_data, message_data
    try:
        if not year_month.isdigit() or len(year_month) != 6:
            await ctx.send("請輸入正確的年份和月份格式，例如：`!anime 202501`")
            return

        # 如果已存在於 server_data，直接加載
        if year_month in server_data:
            bangumi_data = server_data[year_month]
        else:
            # 查詢動畫數據
            bangumi_data = fetch_bangumi_data(year_month)
            if not bangumi_data:
                await ctx.send("未能找到任何動畫數據，請確認輸入的年份和月份是否正確！")
                return

            # 保存數據到 server_data 和文件
            server_data[year_month] = bangumi_data
            save_data_to_file(server_data)

        # 生成 CSV 並提供下載
        file_name = save_to_csv(bangumi_data)
        await ctx.send(f"已生成 {year_month} 的動漫播放列表：", file=discord.File(file_name))

        # 初始化分頁
        embed = generate_embed(bangumi_data, 0)
        message = await ctx.send(embed=embed)

        # 將分頁數據存儲在全局字典中
        message_data[message.id] = {
            "current_page": 0,
            "bangumi_data": bangumi_data
        }

        # 添加翻頁按鈕
        await message.add_reaction("⬅️")
        await message.add_reaction("➡️")

    except Exception as e:
        await ctx.send(f"發生錯誤: {e}")

@bot.event
async def on_reaction_add(reaction, user):
    global reaction_cooldown, message_data

    if user == bot.user:
        return

    # 清理過期的冷卻時間數據
    clean_reaction_cooldown()

    message_id = reaction.message.id
    if message_id not in message_data:
        return

    # 檢查冷卻時間
    now = asyncio.get_event_loop().time()
    if message_id not in reaction_cooldown:
        reaction_cooldown[message_id] = {}

    last_reaction_time = reaction_cooldown[message_id].get(user.id, 0)
    if now - last_reaction_time < 1:  # 設定冷卻時間為 1 秒
        await reaction.remove(user)
        return

    # 更新用戶最後一次反應的時間
    reaction_cooldown[message_id][user.id] = now

    # 翻頁邏輯
    data = message_data[message_id]
    bangumi_data = data["bangumi_data"]
    current_page = data["current_page"]

    if reaction.emoji == "⬅️" and current_page > 0:
        current_page -= 1
    elif reaction.emoji == "➡️" and current_page < len(bangumi_data) - 1:
        current_page += 1
    else:
        await reaction.remove(user)
        return

    # 更新分頁狀態並修改消息
    message_data[message_id]["current_page"] = current_page
    embed = generate_embed(bangumi_data, current_page)
    await reaction.message.edit(embed=embed)
    await reaction.remove(user)

@bot.command()
async def name(ctx, *, anime_title: str):
    global server_data, message_data
    try:
        # 搜索所有年份中包含關鍵字的動畫
        matched_animes = [
            anime
            for year_month, animes in server_data.items()
            for anime in animes
            if anime_title in anime["title"]
        ]

        if not matched_animes:
            await ctx.send(f"未找到名稱包含 `{anime_title}` 的動畫。")
            return

        # 初始化分頁
        embed = generate_embed(matched_animes, 0)
        message = await ctx.send(embed=embed)

        # 將分頁數據存儲在全局字典中
        message_data[message.id] = {
            "current_page": 0,
            "bangumi_data": matched_animes
        }

        # 添加翻頁按鈕
        await message.add_reaction("⬅️")
        await message.add_reaction("➡️")

    except Exception as e:
        await ctx.send(f"發生錯誤: {e}")

# 保存數據到文件
def save_data_to_file(data):
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

# 加載已保存的數據
def load_saved_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}

server_data = load_saved_data()

# 啟動 Bot
bot.run(DISCORD_BOT_TOKEN)
