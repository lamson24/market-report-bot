import math
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import requests
from zoneinfo import ZoneInfo


TELEGRAM_LIMIT = 3500
TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")

ASSETS = [
    {
        "name": "BTC/USD",
        "symbol": "BTC-USD",
        "unit": "USD",
        "kind": "crypto",
    },
    {
        "name": "VANG XAU/USD",
        "symbol": "GC=F",
        "unit": "USD/oz",
        "kind": "commodity",
    },
    {
        "name": "DAU WTI",
        "symbol": "CL=F",
        "unit": "USD/thung",
        "kind": "commodity",
    },
    {
        "name": "DAU BRENT",
        "symbol": "BZ=F",
        "unit": "USD/thung",
        "kind": "commodity",
    },
]


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def fmt_price(value: Optional[float]) -> str:
    if value is None or not math.isfinite(value):
        return "N/A"
    if value >= 1000:
        return f"{value:,.2f}"
    return f"{value:.2f}"


def fetch_chart(symbol: str, range_: str = "3mo", interval: str = "1d") -> Dict:
    encoded = quote(symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
    response = requests.get(
        url,
        params={"range": range_, "interval": interval},
        timeout=20,
        headers={"User-Agent": "market-report-bot/1.0"},
    )
    response.raise_for_status()
    payload = response.json()
    result = payload.get("chart", {}).get("result") or []
    if not result:
        raise RuntimeError(f"No chart data returned for {symbol}")
    return result[0]


def extract_ohlc(chart: Dict) -> List[Dict[str, float]]:
    quote_data = (chart.get("indicators", {}).get("quote") or [{}])[0]
    timestamps = chart.get("timestamp") or []
    rows = []
    for idx, ts in enumerate(timestamps):
        close = value_at(quote_data.get("close"), idx)
        high = value_at(quote_data.get("high"), idx)
        low = value_at(quote_data.get("low"), idx)
        open_ = value_at(quote_data.get("open"), idx)
        if None in (close, high, low, open_):
            continue
        rows.append(
            {
                "time": float(ts),
                "open": float(open_),
                "high": float(high),
                "low": float(low),
                "close": float(close),
            }
        )
    if len(rows) < 30:
        raise RuntimeError("Not enough candles for analysis")
    return rows


def value_at(values: Optional[List[Optional[float]]], idx: int) -> Optional[float]:
    if not values or idx >= len(values):
        return None
    value = values[idx]
    if value is None:
        return None
    return float(value)


def sma(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def rsi(values: List[float], period: int = 14) -> Optional[float]:
    if len(values) <= period:
        return None
    gains = []
    losses = []
    for i in range(-period, 0):
        delta = values[i] - values[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(abs(min(delta, 0.0)))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def levels(rows: List[Dict[str, float]]) -> Tuple[float, float, float, float]:
    recent = rows[-20:]
    support = min(row["low"] for row in recent)
    resistance = max(row["high"] for row in recent)
    last = rows[-1]["close"]
    buffer = max((resistance - support) * 0.18, last * 0.006)
    support_near = max(support, last - buffer)
    resistance_near = min(resistance, last + buffer)
    return support_near, support, resistance_near, resistance


def analyze_asset(asset: Dict) -> str:
    chart = fetch_chart(asset["symbol"])
    rows = extract_ohlc(chart)
    closes = [row["close"] for row in rows]
    last = closes[-1]
    prev = closes[-2]
    change = ((last - prev) / prev) * 100 if prev else 0.0
    sma10 = sma(closes, 10)
    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)
    rsi14 = rsi(closes)
    support_near, support_deep, resistance_near, resistance_far = levels(rows)

    if sma10 and sma20 and last > sma10 > sma20:
        trend = "nghieng tang"
    elif sma10 and sma20 and last < sma10 < sma20:
        trend = "nghieng giam"
    else:
        trend = "di ngang/rung lac"

    if sma50 and last > sma50:
        trend_note = "gia dang nam tren SMA50"
    elif sma50:
        trend_note = "gia dang nam duoi SMA50"
    else:
        trend_note = "chua du du lieu SMA50"

    rsi_text = "N/A" if rsi14 is None else f"{rsi14:.1f}"
    if rsi14 is not None and rsi14 >= 70:
        risk = "RSI cao, canh giac mua duoi va chot loi ngan han."
    elif rsi14 is not None and rsi14 <= 30:
        risk = "RSI thap, canh giac ban duoi va nhip hoi ky thuat."
    else:
        risk = "Theo doi tin vi mo, USD, loi suat va bien dong dia chinh tri."

    if asset["kind"] == "crypto":
        extra_risk = "BTC thuong bien dong manh ngoai gio My; nen giam khoi luong khi gia di sat can."
    elif "DAU" in asset["name"]:
        extra_risk = "Dau nhay cam voi tin OPEC, ton kho EIA/API va rui ro Trung Dong."
    else:
        extra_risk = "Vang nhay cam voi USD, loi suat trai phieu va du lieu lam phat."

    return (
        f"{asset['name']}\n"
        f"- Gia tham chieu: {fmt_price(last)} {asset['unit']} ({change:+.2f}% so voi phien truoc)\n"
        f"- Xu huong: {trend}; {trend_note}; RSI14 {rsi_text}\n"
        f"- Ho tro: {fmt_price(support_near)} / {fmt_price(support_deep)}\n"
        f"- Khang cu: {fmt_price(resistance_near)} / {fmt_price(resistance_far)}\n"
        f"- Kich ban long: uu tien khi gia giu tren {fmt_price(support_near)} va co nen xac nhan tang; muc tieu gan {fmt_price(resistance_near)}.\n"
        f"- Kich ban short: canh khi gia mat {fmt_price(support_near)} hoac bi tu choi tai {fmt_price(resistance_near)}; muc tieu gan {fmt_price(support_deep)}.\n"
        f"- Rui ro: {risk} {extra_risk}"
    )


def build_report() -> str:
    now = datetime.now(TIMEZONE)
    parts = [
        f"BAO CAO THI TRUONG 3 NHOM TAI SAN - {now:%d/%m/%Y %H:%M} VN",
        "Khung tham chieu: du lieu ngay gan nhat tu Yahoo Finance.",
    ]
    for asset in ASSETS:
        try:
            parts.append(analyze_asset(asset))
        except Exception as exc:
            parts.append(f"{asset['name']}\n- Khong lay duoc du lieu: {exc}")
    parts.append(
        "Tong ket: Uu tien giao dich theo vung xac nhan, khong mua/ban duoi khi gia sat khang cu/ho tro. "
        "Day la thong tin tham khao, khong phai loi khuyen tai chinh."
    )
    return "\n\n".join(parts)


def send_telegram(text: str) -> None:
    token = require_env("TELEGRAM_BOT_TOKEN")
    chat_id = require_env("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    chunks = [text[i : i + TELEGRAM_LIMIT] for i in range(0, len(text), TELEGRAM_LIMIT)]
    for chunk in chunks:
        response = requests.post(url, data={"chat_id": chat_id, "text": chunk}, timeout=20)
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram rejected message: {payload}")


def main() -> int:
    report = build_report()
    print(report)
    send_telegram(report)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
