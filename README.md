# Telegram market report automation

Automation nay gui bao cao BTC/USD, vang XAU/USD, dau WTI va dau Brent qua Telegram luc 07:00 va 22:00 hang ngay theo gio Viet Nam.

## Cach dua len GitHub Actions

1. Tao mot repository moi tren GitHub, vi du `market-report-bot`.
2. Day cac file trong thu muc nay len repository do.
3. Vao repository tren GitHub:
   `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`.
4. Them 2 secret:
   - `TELEGRAM_BOT_TOKEN`: token bot Telegram cua ban.
   - `TELEGRAM_CHAT_ID`: chat ID Telegram cua ban.
5. Vao tab `Actions`, chon workflow `Market report Telegram`, bam `Run workflow` de test ngay.

Sau khi test thanh cong, GitHub Actions se tu chay theo lich:

- 00:00 UTC = 07:00 gio Viet Nam
- 15:00 UTC = 22:00 gio Viet Nam

## Chay thu tren may local

PowerShell:

```powershell
$env:TELEGRAM_BOT_TOKEN="your_bot_token"
$env:TELEGRAM_CHAT_ID="your_chat_id"
python scripts/send_market_report.py
```

Khong commit token Telegram vao GitHub. Chi luu token trong GitHub Secrets.
