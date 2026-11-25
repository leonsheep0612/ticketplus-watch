# Ticket Plus 釋票通知

監控遠大售票 [Ticket Plus](https://ticketplus.com.tw) 的演唱會票區，票區從售完變成有票（退票、清票釋出）時用 Telegram 通知。

- 只讀售票網站公開的票數資料，**不登入、不下單、不碰驗證碼**，買票請自己到網站操作。
- GitHub Actions 每 5 分鐘執行一次（GitHub 排程尖峰時常延遲，不保證準時）。

## 使用方式（Telegram）

| 傳給機器人 | 作用 |
|---|---|
| 演唱會名稱，例如 `田馥甄`、`高明駿 台北站` | 搜尋並加入監控；多個詞要全部符合，找到多個活動時點 `/w_…` 選一個 |
| `https://ticketplus.com.tw/activity/…` | 直接用網址加入 |
| `/list` | 監控中的活動與目前票況 |
| `/stop_代碼` | 取消監控（`/list` 裡可以直接點） |
| `/help` | 使用方式 |

機器人只接受 `TELEGRAM_CHAT_ID` 那個聊天室的訊息，其他人傳的會略過。

## 設定

1. Telegram 找 @BotFather 傳 `/newbot` 建立機器人，取得 token。
2. 傳一則訊息給機器人，打開 `https://api.telegram.org/bot<token>/getUpdates` 找到 `chat.id`。
3. repo 的 Settings → Secrets and variables → Actions 新增 `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`。
4. Actions 頁面手動執行 **Ticket Plus Watch**，`test` 填 `1` 會推播一則測試訊息。

## 檔案

- `ticketplus_watch.py`：主程式（讀 Telegram 指令 → 查票區 → 推播釋票）
- `ticketplus_watch.json`：監控清單，由機器人維護，也可以手動編輯；`areas` 填關鍵字只看名稱符合的票區
- `data/ticketplus_state.json`：已通知的票區與 Telegram 訊息進度，workflow 自動更新
