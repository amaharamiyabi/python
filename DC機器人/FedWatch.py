import discord
from discord.ext import commands, tasks
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime, timedelta, time

# 配置 Discord Bot Token 和頻道 ID 列表
DISCORD_TOKEN = "MTMyNjQ2MDk5MDM3MTQwMTc1MA.G_4Ro0.avCCvot-Zm5Cl2ESFKqZ7eShw_5ReM9s-Owm8I"
CHANNEL_IDS = [1326464493135462483, 679226040089837593]  # 替換成你的目標頻道 ID 列表（數字）

# 配置 ChromeOptions
options = Options()
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--headless")
options.add_argument("--use-gl=angle")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

# 定義抓取倒數時間的函數
def fetch_countdown():
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        url = "https://www.cmegroup.com/cn-t/markets/interest-rates/cme-fedwatch-tool.html"
        driver.get(url)
        countdown = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "countdownClock"))
        )

        days = int(countdown.find_element(By.CLASS_NAME, "days").find_element(By.TAG_NAME, "span").text)
        hours = int(countdown.find_element(By.CLASS_NAME, "hours").find_element(By.TAG_NAME, "span").text)
        minutes = int(countdown.find_element(By.CLASS_NAME, "minutes").find_element(By.TAG_NAME, "span").text)
        seconds = int(countdown.find_element(By.CLASS_NAME, "seconds").find_element(By.TAG_NAME, "span").text)

        countdown_text = f"倒數時間: {days}天 {hours}小時 {minutes}分鐘 {seconds}秒"

        # 計算活動日期
        now = datetime.now()
        event_date = now + timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
        event_date_text = event_date.strftime("%Y 年 %m 月 %d 日 %H:%M:%S")

        return countdown_text, event_date_text
    except Exception as e:
        return f"抓取時間失敗，錯誤原因: {e}", None
    finally:
        driver.quit()

# 推斷當前日期的函數
def get_current_date():
    now = datetime.now()
    return f"今天是 {now.year} 年 {now.month} 月 {now.day} 日"

# 創建 Discord Bot
intents = discord.Intents.default()
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 定時任務，每週一早上 8 點執行
@tasks.loop(minutes=1)
async def weekly_task():
    now = datetime.now()
    if now.weekday() == 0 and now.hour == 8 and now.minute == 0:  # 每週一早上 8 點觸發
        countdown_text, event_date_text = fetch_countdown()
        current_date = get_current_date()
        for channel_id in CHANNEL_IDS:
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(f"{current_date}\n{countdown_text}\n活動日期: {event_date_text}")

@bot.event
async def on_ready():
    print(f"機器人已登入為 {bot.user}")
    if not weekly_task.is_running():
        weekly_task.start()

# 測試命令（手動觸發倒數提醒）
@bot.command()
async def test(ctx):
    print("!test 指令已觸發")  # 確認指令觸發
    countdown_text, event_date_text = fetch_countdown()
    current_date = get_current_date()
    await ctx.send(f"{current_date}\n{countdown_text}\n活動日期: {event_date_text}")

# 啟動 Bot
bot.run(DISCORD_TOKEN)