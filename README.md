# Ticket Plus 釋票通知

輸入 Ticket Plus 活動網址，定期查詢所有公開場次的票種與票區；有票時透過 Telegram 通知，不會自動購票。需要 Python 3.9 以上，不需安裝其他套件。

## 設定 Telegram

1. 在 Telegram 找 [@BotFather](https://t.me/BotFather)，建立 bot 並取得 token。
2. 傳一則訊息給你的 bot，然後在瀏覽器開啟 `https://api.telegram.org/bot<你的 token>/getUpdates`，從結果中的 `message.chat.id` 取得 chat ID。若要傳到群組，先將 bot 加入群組並傳訊息，再取得該群組的 chat ID。
3. 在執行程式的終端機設定環境變數（不要把 token 放進程式或提交到 Git）：

   ```sh
   export TELEGRAM_BOT_TOKEN='你的 bot token'
   export TELEGRAM_CHAT_ID='你的 chat ID'
   ```

Bot token 是密碼，請勿分享；如已洩漏，請透過 BotFather 撤銷並重新產生。

## 開始監控

```sh
python3 watch.py 'https://ticketplus.com.tw/activity/活動ID'
```

也可以執行 `python3 watch.py` 後貼上網址。預設每 60 秒檢查一次；可用 `--interval 120` 調整秒數，最短 30 秒。程式必須持續執行才能通知，按 Ctrl+C 結束。Windows 使用者可依其終端機方式設定相同環境變數。

啟動時若已有票也會通知；同一票種持續有票時不重複通知，售完後再次有票才會再通知。重新啟動會重新檢查並通知。查詢或 Telegram 失敗時會顯示錯誤並逐步延長重試間隔，成功後恢復設定的間隔。

只支援 `https://ticketplus.com.tw/activity/<活動 ID>` 活動網址，監控所有公開場次，無法保證通知時仍有票、符合購票資格或能成功購票。Ticket Plus 的非公開票況介面可能變更、限制流量或拒絕請求，請遵守網站規範；請勿使用過短間隔。

## 測試

```sh
python3 -m unittest -v test_watch
```
