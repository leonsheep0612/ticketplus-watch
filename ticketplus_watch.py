import os
import re
import json
import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}

# 監控遠大售票 Ticket Plus 指定活動有沒有釋票：票區從售完變成有票時用 Telegram 推播，買票由自己手動操作
# 只讀售票網站公開的票數 API，不登入、不下單
# 資料來源：getS3 取活動清單、場次與票區（靜態 JSON），get?ticketAreaId= 取各票區的狀態與剩餘張數
# 有設 Telegram 時，每次執行會先讀你傳給機器人的訊息：傳演唱會名稱就加入監控、/list 看清單、/stop_xxx 取消
API = "https://apis.ticketplus.com.tw/config/api/v1"
API_HEADERS = {**HEADERS, "Referer": "https://ticketplus.com.tw/"}
# count 是剩餘張數；票還很多時網站不給實際數字，固定回 999999
PLENTY = 999999

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(ROOT, "ticketplus_watch.json")
STATE_PATH = os.path.join(ROOT, "data", "ticketplus_state.json")
# TEST = 1 時不管有沒有變化都推播一次，用來確認推播與 Ticket Plus 連得到
TEST = os.environ.get("TEST", "").strip() == "1"

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

HELP = ("🎫 歡迎使用 Ticket Plus 遠大售票 釋票通知！\n"
        "\n"
        "【加入監控】直接傳演唱會名稱，例如：\n"
        "  田馥甄\n"
        "  YOASOBI\n"
        "  高明駿 台北站（多個詞要全部符合）\n"
        "找到好幾個活動時，點要監控的那個 /w_… 就好；也可以直接貼 ticketplus.com.tw/activity/… 網址。\n"
        "\n"
        "【其他指令】\n"
        "  /list 看監控中的活動與目前票況\n"
        "  /stop_代碼 取消監控（/list 裡可以直接點）\n"
        "  /help 再看一次這段說明\n"
        "\n"
        "票區從售完變成有票時會通知你，買票請自己到網站操作。\n"
        "※ 機器人每 5 分鐘左右才讀一次訊息，傳完請稍等幾分鐘再看回覆")
# 機器人簡介與指令選單；內容有改就把版本加 1，下次執行會重新設定
BOT_PROFILE_VERSION = 1
BOT_DESCRIPTION = ("傳演唱會名稱給我，遠大售票（Ticket Plus）有人退票、清票釋出時通知你。\n"
                   "按下方「開始」看使用方式。")
BOT_SHORT_DESCRIPTION = "遠大售票 Ticket Plus 釋票通知：傳演唱會名稱就幫你盯票"
BOT_COMMANDS = [{"command": "list", "description": "監控中的活動與目前票況"},
                {"command": "help", "description": "使用方式"}]


def call(endpoint, **params):
    """呼叫 Ticket Plus API，逾時或連線錯誤重試 3 次，仍失敗回傳 None"""
    for _ in range(3):
        try:
            r = requests.get(f"{API}/{endpoint}", params=params, headers=API_HEADERS, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            err = e
    print(f"⚠️ Ticket Plus 查詢失敗 {endpoint} {params}：{err}")
    return None


def tg(method, **payload):
    """呼叫 Telegram Bot API，失敗回傳 None"""
    try:
        r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/{method}", json=payload, timeout=30)
        if r.ok:
            return r.json().get("result")
        print(f"❌ Telegram {method} 失敗：{r.status_code} {r.text}")
    except Exception as e:
        print(f"❌ Telegram {method} 失敗：{e}")
    return None


def notify(text):
    ok = tg("sendMessage", chat_id=TG_CHAT_ID, text=text[:4000], disable_web_page_preview=True) is not None
    print("✅ Telegram 推播成功" if ok else "❌ Telegram 推播失敗")
    return ok


def event_id(url):
    m = re.search(r"activity/([0-9a-f]{32})", url)
    return m.group(1) if m else None


def event_areas(event):
    """一個活動的所有票區 [{id, event, session, area, price, status, count, url}]；查不到回傳 None"""
    eid = event_id(event["url"])
    if not eid:
        print(f"⚠️ 網址看不出活動代碼：{event['url']}")
        return None
    sessions = call("getS3", path=f"event/{eid}/sessions.json")
    areas = call("getS3", path=f"event/{eid}/ticketAreas.json")
    if not sessions or not areas:
        return None
    sessions = {s["sessionId"]: s for s in sessions.get("sessions", [])}
    keywords = event.get("areas") or []
    wanted = [a for a in areas.get("ticketAreas", [])
              if not a.get("hidden") and (not keywords or any(k in a["name"] for k in keywords))]
    if not wanted:
        return []
    live = call("get", ticketAreaId=",".join(a["ticketAreaId"] for a in wanted))
    if not live or live.get("errCode") != "00":
        return None
    live = {a["id"]: a for a in live["result"].get("ticketArea", [])}
    # 場次日期、時間是「起 ~ 迄」，同一天的只顯示一次
    span = lambda v: " ~ ".join(dict.fromkeys(p.strip() for p in (v or "").split("~")))
    result = []
    for a in wanted:
        s = sessions.get(a["sessionId"], {})
        info = live.get(a["ticketAreaId"], {})
        result.append({"id": a["ticketAreaId"], "event": s.get("name", eid), "session": f"{span(s.get('date'))} {span(s.get('time'))}".strip(),
                       "area": a["name"], "price": a.get("price"), "status": info.get("status", ""),
                       "count": int(info.get("count") or 0), "url": f"https://ticketplus.com.tw/activity/{eid}"})
    return result


def is_available(a):
    """開賣中且有剩餘張數才算有票"""
    return a["status"] == "onsale" and a["count"] > 0


def format_areas(areas):
    """依活動分組列出票區與張數"""
    lines = []
    for url in dict.fromkeys(a["url"] for a in areas):
        group = [a for a in areas if a["url"] == url]
        lines.append(f"\n{group[0]['event']}")
        lines += [f"・{a['session']} {a['area']} ${a['price']}："
                  + ("大量" if a["count"] >= PLENTY else f"{a['count']} 張" if is_available(a) else "售完" if a["status"] == "onsale" else "未開賣")
                  for a in group]
        lines.append(url)
    return lines


def handle_commands(events, state):
    """讀 Telegram 新訊息並執行指令；回傳監控清單有沒有改"""
    updates = tg("getUpdates", offset=state.get("tg_offset", 0) + 1, timeout=0, allowed_updates=["message"])
    if not updates:
        return False
    changed = False
    catalog = None
    for u in updates:
        state["tg_offset"] = u["update_id"]
        msg = u.get("message") or {}
        # 機器人是公開的，只接受自己的聊天室，其他人傳的訊息直接略過
        if str(msg.get("chat", {}).get("id")) != TG_CHAT_ID or not msg.get("text"):
            continue
        text = msg["text"].strip()
        print(f"Telegram 指令：{text}")
        reply = lambda t: tg("sendMessage", chat_id=TG_CHAT_ID, text=t[:4000], disable_web_page_preview=True)

        if text in ("/start", "/help"):
            reply(HELP)
            continue
        if text in ("/list", "清單"):
            if not events:
                reply("目前沒有監控任何活動，傳演唱會名稱就能加入")
                continue
            lines = ["📋 監控中的活動"]
            for e in events:
                areas = event_areas(e)
                lines += format_areas(areas) if areas else [f"\n{e.get('title') or e['url']}（查不到票區）"]
                lines.append(f"取消：/stop_{event_id(e['url'])[:8]}")
            reply("\n".join(lines))
            continue
        m = re.fullmatch(r"/stop_([0-9a-f]{8})", text)
        if m:
            gone = [e for e in events if (event_id(e["url"]) or "").startswith(m.group(1))]
            events[:] = [e for e in events if e not in gone]
            changed |= bool(gone)
            reply(f"🛑 已取消監控：{gone[0].get('title') or gone[0]['url']}" if gone else "找不到這個活動，可能已經取消了")
            continue

        if catalog is None:
            catalog = (call("getS3", path="main/mainEvents.json") or {}).get("allEventMainPageInfo", {})
        m = re.fullmatch(r"/w_([0-9a-f]{8})", text)
        eid = event_id(text)
        if m:
            found = [(h, e) for h, e in catalog.items() if h.startswith(m.group(1))]
        elif eid:
            found = [(eid, catalog.get(eid, {}))]
        else:
            # 每個詞都要出現在活動名稱裡，不分大小寫
            words = text.lower().split()
            found = [(h, e) for h, e in catalog.items()
                     if not e.get("hidden") and all(w in e.get("title", "").lower() for w in words)]
        if not found:
            reply(f"找不到「{text}」的活動。可以換個關鍵字，或直接貼活動網址")
            continue
        if len(found) > 1:
            lines = [f"找到 {len(found)} 個活動，點要監控的那個："]
            lines += [f"\n{e.get('title')}（{e.get('start_date', '')}）\n/w_{h[:8]}" for h, e in found[:15]]
            reply("\n".join(lines))
            continue

        h, info = found[0]
        url = f"https://ticketplus.com.tw/activity/{h}"
        if any(event_id(e["url"]) == h for e in events):
            reply(f"已經在監控了：{info.get('title') or url}")
            continue
        new = {"url": url, "title": info.get("title", ""), "areas": []}
        areas = event_areas(new)
        if areas is None:
            reply(f"查不到這個活動的票區，先不加入：{url}")
            continue
        events.append(new)
        changed = True
        # 現在已經有票的票區直接在回覆裡列出，記成已通知，之後只推真正的釋票
        state["available"] = sorted(set(state.get("available", [])) | {a["id"] for a in areas if is_available(a)})
        reply("\n".join(["✅ 已加入監控，票區從售完變成有票時會通知你", "目前票況："]
                        + format_areas(areas) + [f"取消：/stop_{h[:8]}"]))
    return changed


def main():
    if not TG_TOKEN or not TG_CHAT_ID:
        raise SystemExit("❌ 找不到 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID，請在 .env 設定（參考 .env.example）")
    # 監控清單由 Telegram 指令維護，第一次執行還沒有檔案
    config = {"events": []}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config = json.load(f)
    events = config.setdefault("events", [])
    state = {}
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            state = json.load(f)

    if state.get("tg_profile") != BOT_PROFILE_VERSION:
        ok = all(tg(method, **payload) is not None for method, payload in (
            ("setMyDescription", {"description": BOT_DESCRIPTION}),
            ("setMyShortDescription", {"short_description": BOT_SHORT_DESCRIPTION}),
            ("setMyCommands", {"commands": BOT_COMMANDS})))
        if ok:
            state["tg_profile"] = BOT_PROFILE_VERSION
            print("✅ 已設定 Telegram 機器人簡介與指令選單")

    if handle_commands(events, state):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=1)
            f.write("\n")

    def save(ids):
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        # 不記檢查時間，有票的票區與 Telegram 訊息都沒變時檔案內容就不變
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump({**state, "available": sorted(ids)}, f, ensure_ascii=False, indent=1)

    if not events:
        print("沒有要監控的活動")
        save(set())
        return

    results = [event_areas(e) for e in events]
    failed = [e["url"] for e, r in zip(events, results) if r is None]
    areas = [a for r in results if r for a in r]
    available = [a for a in areas if is_available(a)]
    print(f"監控 {len(events)} 個活動、{len(areas)} 個票區，查詢失敗 {len(failed)} 個活動；有票的票區 {len(available)} 個")
    for a in areas:
        print(f"  {a['event']} {a['session']} {a['area']}：{a['status']} × {a['count']}")

    old = set(state.get("available", []))
    # 查詢失敗的活動沿用上次的紀錄，免得下次查到又當成新釋票
    failed_ids = {i for i in old if not any(i == a["id"] for a in areas)} if failed else set()
    now = {a["id"] for a in available} | failed_ids
    new = [a for a in available if a["id"] not in old]

    if not new and not TEST:
        save(now)
        print("沒有新釋出的票區，不推播")
        return

    lines = ["🎫 Ticket Plus " + ("有新釋票" if new else "目前有票的票區")] + format_areas(new or available)
    if TEST:
        lines.append(f"\n（測試推播：Ticket Plus 連線正常，監控 {len(areas)} 個票區，查詢失敗 {len(failed)} 個活動）")
    if notify("\n".join(lines)):
        save(now)
    else:
        # 沒推出去的釋票不記進已通知，下次一起推
        save(now - {a["id"] for a in new})


if __name__ == "__main__":
    main()
