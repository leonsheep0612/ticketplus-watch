# Ticket Plus 釋票通知

監控遠大售票 [Ticket Plus](https://ticketplus.com.tw) 的演唱會票區，票區從售完變成有票（退票、清票釋出）時用 Telegram 通知。

- 只讀售票網站公開的票數資料，**不登入、不下單、不碰驗證碼**，買票請自己到網站操作。
- 在自己的 Windows 電腦上用工作排程器每 5 分鐘執行一次，**電腦要開著才會通知**。
- 不能放在 GitHub Actions：Ticket Plus 會擋國外資料中心的連線（回 403）。

## 使用方式（Telegram）

| 傳給機器人 | 作用 |
|---|---|
| 演唱會名稱，例如 `田馥甄`、`高明駿 台北站` | 搜尋並加入監控；多個詞要全部符合，找到多個活動時點 `/w_…` 選一個 |
| `https://ticketplus.com.tw/activity/…` | 直接用網址加入 |
| `/list` | 監控中的活動與目前票況 |
| `/stop_代碼` | 取消監控（`/list` 裡可以直接點） |
| `/help` | 使用方式 |

機器人只接受 `TELEGRAM_CHAT_ID` 那個聊天室的訊息，其他人傳的會略過。每 5 分鐘才讀一次訊息，回覆會慢幾分鐘。

## 安裝（換電腦時照做一次）

1. 安裝 Python 3，安裝時勾選 **Add python.exe to PATH**，再執行 `pip install -r requirements.txt`。
2. 把 `.env.example` 複製成 `.env`，填入：
   - `TELEGRAM_BOT_TOKEN`：@BotFather 給的 token
   - `TELEGRAM_CHAT_ID`：傳一則訊息給機器人後，打開 `https://api.telegram.org/bot<token>/getUpdates` 找到的 `chat.id`
3. 在這個資料夾開 PowerShell 執行 `.\install_task.ps1`，建立每 5 分鐘的工作排程。
4. 換電腦時，舊電腦執行 `.\install_task.ps1 -Uninstall`；要沿用監控清單就把 `ticketplus_watch.json` 和 `data\` 一起複製過去。

手動執行一次：`pythonw run_local.pyw`，結果看 `logs\watch.log`。

## 檔案

- `ticketplus_watch.py`：主程式（讀 Telegram 指令 → 查票區 → 推播釋票）
- `run_local.pyw`：本機啟動程式（讀 `.env`、不走 proxy、輸出寫到 `logs\watch.log`）
- `install_task.ps1`：建立／移除 Windows 工作排程
- `ticketplus_watch.json`：監控清單，由機器人維護，也可以手動編輯；`areas` 填關鍵字只看名稱符合的票區
- `data\ticketplus_state.json`：已通知的票區與 Telegram 訊息進度

`.env`、`ticketplus_watch.json`、`data\`、`logs\` 只存在本機，不會進 git。
