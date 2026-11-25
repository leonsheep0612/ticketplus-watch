# 在自己電腦上執行釋票通知（給 Windows 工作排程器每 5 分鐘呼叫）
# Ticket Plus 會擋 GitHub 等國外資料中心的連線，所以改在台灣的電腦上跑
# .pyw 用 pythonw 執行，不會跳出黑色視窗；輸出寫到 logs/watch.log
import os
import sys
import traceback
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

# Telegram 金鑰放在同資料夾的 .env（不會進 git），格式：TELEGRAM_BOT_TOKEN=...
env_path = os.path.join(ROOT, ".env")
if os.path.exists(env_path):
    with open(env_path, encoding="utf-8-sig") as f:
        for line in f:
            key, sep, value = line.strip().partition("=")
            if sep and not key.startswith("#"):
                os.environ[key.strip()] = value.strip().strip('"').strip("'")

# 不走系統 proxy：公司 proxy 需要帳密驗證會回 407，直接連 Ticket Plus 和 Telegram 都通
for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(key, None)
os.environ["NO_PROXY"] = os.environ["no_proxy"] = "*"

LOG_DIR = os.path.join(ROOT, "logs")
LOG_PATH = os.path.join(LOG_DIR, "watch.log")
os.makedirs(LOG_DIR, exist_ok=True)
# 紀錄超過 1 MB 就換新檔，舊的留一份 watch.old.log
if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 1_000_000:
    os.replace(LOG_PATH, os.path.join(LOG_DIR, "watch.old.log"))

with open(LOG_PATH, "a", encoding="utf-8") as log:
    sys.stdout = sys.stderr = log
    print(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} =====")
    try:
        import ticketplus_watch
        ticketplus_watch.main()
    except SystemExit as e:
        if e.code not in (None, 0):
            print(e.code)
    except Exception:
        traceback.print_exc()
