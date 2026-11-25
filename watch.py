#!/usr/bin/env python3
import argparse
from http.client import HTTPException
import json
import os
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


API = "https://apis.ticketplus.com.tw/config/api/v1"
HEADERS = {
    "Accept": "application/json",
    "Origin": "https://ticketplus.com.tw",
    "Referer": "https://ticketplus.com.tw/",
    "User-Agent": "ticketplus-watch/1.0",
}


class WatchError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = build_opener(NoRedirect())


def event_id_from_url(url):
    parts = urlsplit(url.strip())
    match = re.fullmatch(r"/activity/([0-9a-fA-F]{32})/?", parts.path)
    if (parts.scheme != "https" or parts.netloc.lower() not in
            ("ticketplus.com.tw", "www.ticketplus.com.tw") or not match):
        raise ValueError("請輸入 Ticket Plus 活動網址：https://ticketplus.com.tw/activity/<活動 ID>")
    return match.group(1).lower()


def request_json(url, data=None, headers=None):
    request = Request(url, data=data, headers=headers or HEADERS)
    try:
        with OPENER.open(request, timeout=15) as response:
            result = json.load(response)
    except HTTPError as exc:
        raise WatchError(f"HTTP {exc.code}") from None
    except (URLError, TimeoutError, OSError, ValueError, HTTPException):
        raise WatchError("網路錯誤或伺服器回傳無效資料") from None
    if not isinstance(result, dict):
        raise WatchError("伺服器回傳無效資料")
    return result


def catalog(event_id):
    result = {}
    for key in ("sessions", "ticketAreas", "products"):
        query = urlencode({"path": f"event/{event_id}/{key}.json"})
        data = request_json(f"{API}/getS3?{query}")
        if data.get("errCode") not in (None, "00") or not isinstance(data.get(key), list):
            raise WatchError(f"無法讀取活動目錄：{key}")
        result[key] = data[key]
    return result


def available_tickets(event_id):
    data = catalog(event_id)
    sessions = {s["sessionId"]: s for s in data["sessions"]
                if isinstance(s, dict) and s.get("sessionId") and not s.get("hidden")}
    areas = {a["ticketAreaId"]: a for a in data["ticketAreas"]
             if isinstance(a, dict) and a.get("ticketAreaId") and not a.get("hidden")
             and a.get("sessionId") in sessions}
    products = {}
    for product in data["products"]:
        if not isinstance(product, dict) or not product.get("productId") or product.get("hidden"):
            continue
        area_id = product.get("ticketAreaId")
        area = areas.get(area_id) if area_id else None
        session_id = product.get("sessionId") or (area or {}).get("sessionId")
        if session_id not in sessions or (area_id and not area):
            continue
        products[product["productId"]] = (product, area, sessions[session_id])
    if not products:
        raise WatchError("活動目錄沒有可監控的票種，稍後重試")
    query = {"productId": ",".join(products)}
    if areas:
        query["ticketAreaId"] = ",".join(areas)
    response = request_json(f"{API}/get?{urlencode(query)}")
    result = response.get("result")
    if response.get("errCode") not in (None, "00") or not isinstance(result, dict):
        raise WatchError("無法讀取即時票況")
    product_info = index_status(result, "product", products)
    area_info = index_status(result, "ticketArea", areas)
    available = {}
    for product_id, (product, area, session) in products.items():
        if not ready(product_info[product_id], "productLimit"):
            continue
        if area and not ready(area_info[area["ticketAreaId"]], "ticketAreaLimit"):
            continue
        available[product_id] = " / ".join(
            str(name) for name in (session.get("name"), session.get("date"), session.get("time"),
                                   area.get("name") if area else None, product.get("name"))
            if name
        )
    return available


def index_status(result, key, expected):
    entries = result.get(key)
    if not expected:
        return {}
    if not isinstance(entries, list):
        raise WatchError("即時票況資料不完整")
    indexed = {entry.get("id"): entry for entry in entries if isinstance(entry, dict)}
    if not expected.keys() <= indexed.keys():
        raise WatchError("即時票況資料不完整")
    return indexed


def ready(info, limit_key):
    if info.get("status") != "onsale":
        return False
    if info.get(limit_key):
        count = info.get("count")
        if not isinstance(count, (int, float)):
            raise WatchError("即時庫存資料不完整")
        return count > 0
    return True


def notify(token, chat_id, url, tickets):
    lines = []
    length = 0
    for name in tickets.values():
        line = f"• {name}"
        if length + len(line) + 1 > 1500:
            break
        lines.append(line)
        length += len(line) + 1
    if len(lines) < len(tickets):
        lines.append(f"另有 {len(tickets) - len(lines)} 個票種，請至活動頁查看。")
    text = "🎫 Ticket Plus 有票了！\n" + "\n".join(lines) + f"\n{url}"
    body = urlencode({"chat_id": chat_id, "text": text}).encode()
    result = request_json(f"https://api.telegram.org/bot{token}/sendMessage", body,
                          {"Content-Type": "application/x-www-form-urlencoded"})
    if result.get("ok") is not True:
        raise WatchError("Telegram 通知失敗")


def watch(event_id, url, token, chat_id, interval):
    notified = set()
    delay = interval
    while True:
        try:
            available = available_tickets(event_id)
            current = set(available)
            notified.intersection_update(current)
            new = {key: value for key, value in available.items() if key not in notified}
            if new:
                notify(token, chat_id, url, new)
                notified.update(new)
                print(f"已通知 {len(new)} 個有票的票種。", flush=True)
            else:
                print(f"檢查完成，目前有票的票種：{len(current)}", flush=True)
            delay = interval
        except WatchError as exc:
            print(f"檢查或通知失敗：{exc}；{delay} 秒後重試。", file=sys.stderr, flush=True)
            time.sleep(delay)
            delay = min(max(delay * 2, interval), max(900, interval))
            continue
        time.sleep(delay)


def main():
    parser = argparse.ArgumentParser(description="監控 Ticket Plus 活動並透過 Telegram 通知")
    parser.add_argument("url", nargs="?", help="Ticket Plus 活動網址；省略時互動輸入")
    parser.add_argument("--interval", type=int, default=60, help="查詢間隔（秒，最少 30，預設 60）")
    args = parser.parse_args()
    if args.interval < 30:
        parser.error("查詢間隔至少 30 秒")
    try:
        url = (args.url or input("請輸入 Ticket Plus 活動網址：")).strip()
        event_id = event_id_from_url(url)
    except (ValueError, EOFError) as exc:
        parser.error(str(exc) or "未輸入活動網址")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token) or not re.fullmatch(r"-?[0-9]+|@[A-Za-z0-9_]+", chat_id):
        parser.error("請設定有效的 TELEGRAM_BOT_TOKEN 與 TELEGRAM_CHAT_ID 環境變數")
    url = f"https://ticketplus.com.tw/activity/{event_id}"
    print("開始監控，按 Ctrl+C 結束。", flush=True)
    try:
        watch(event_id, url, token, chat_id, args.interval)
    except KeyboardInterrupt:
        print("\n已停止監控。")


if __name__ == "__main__":
    main()
