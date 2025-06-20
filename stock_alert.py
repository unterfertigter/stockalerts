from email.mime.text import MIMEText
import os
import time
import requests
from bs4 import BeautifulSoup
import json
import datetime
import smtplib
import pytz

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))  # seconds
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
CONFIG_PATH = os.getenv("CONFIG_PATH", "config.json")
MAX_FAIL_COUNT = int(os.getenv("MAX_FAIL_COUNT", "3"))

print(f"CHECK_INTERVAL = {CHECK_INTERVAL}")
print(f"EMAIL_FROM = {EMAIL_FROM}")
print(f"EMAIL_TO = {EMAIL_TO}")
print(f"SMTP_SERVER = {SMTP_SERVER}")
print(f"SMTP_PORT = {SMTP_PORT}")
print(f"SMTP_USERNAME = {SMTP_USERNAME}")
print(f"SMTP_PASSWORD = {'***' if SMTP_PASSWORD else None}")
print(f"CONFIG_PATH = {CONFIG_PATH}")
print(f"MAX_FAIL_COUNT = {MAX_FAIL_COUNT}")

if not all([EMAIL_TO, EMAIL_FROM, SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD]):
    raise Exception("Missing required environment variables.")


def load_config(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Config file not found: {path}")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing config file '{path}': {e}")
        exit(1)


def get_tradegate_url(isin):
    return f"https://www.tradegate.de/orderbuch_umsaetze.php?isin={isin}"


def get_stock_price(isin):
    url = get_tradegate_url(isin)
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    tbody = soup.find("tbody", {"id": "umsaetze_body"})
    if tbody:
        first_row = tbody.find("tr")
        if first_row:
            cols = first_row.find_all("td")
            if len(cols) >= 5:
                price_text = cols[4].text.strip().replace("\xa0", "").replace(",", ".")
                try:
                    return float(price_text)
                except Exception:
                    print("Could not parse price:", price_text)
    print("Could not find price on page.")
    return None


def send_email(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    except Exception as e:
        log(f"Failed to send email: {e}")


def log(msg):
    print(f"[{datetime.datetime.now().isoformat(sep=' ', timespec='seconds')}] {msg}")


def main():
    config = load_config(CONFIG_PATH)
    active_alerts = config.copy()
    
    # Fail count to track consecutive failures
    fail_count = 0

    log(f"Monitoring {len(active_alerts)} ISIN(s) every {CHECK_INTERVAL} seconds. Max fail count: {MAX_FAIL_COUNT}")

    cet = pytz.timezone("Europe/Berlin")
    market_open = datetime.time(7, 30)
    market_close = datetime.time(22, 0)

    while active_alerts:
        now_cet = datetime.datetime.now(cet).time()
        if market_open <= now_cet <= market_close:
            # Track which ISINs have already triggered an alert
            to_remove = []
            for entry in active_alerts:
                isin = entry["isin"]
                upper_threshold = entry.get("upper_threshold")
                lower_threshold = entry.get("lower_threshold")
                price = get_stock_price(isin)
                if price is not None:
                    log(f"Current price for ISIN {isin}: {price}")
                    fail_count = 0  # Reset fail count on success
                    alert = False
                    alert_reason = ""
                    if upper_threshold is not None and price >= upper_threshold:
                        alert = True
                        alert_reason = f"reached or exceeded upper threshold {upper_threshold}"
                    if lower_threshold is not None and price <= lower_threshold:
                        alert = True
                        alert_reason = f"reached or fell below lower threshold {lower_threshold}"
                    if alert:
                        send_email(
                            f"Stock Alert: {isin} {alert_reason} (price: {price})",
                            f"The stock with ISIN {isin} {alert_reason}. Current price: {price}.",
                        )
                        log(f"Alert sent for {isin} ({alert_reason}). Skipping this ISIN from now on.")
                        to_remove.append(entry)
                else:
                    log(f"Failed to get stock price for ISIN {isin}.")
                    send_email(
                        f"Stock Alert: Failed to retrieve price for {isin}",
                        f"The service failed to retrieve the stock price for ISIN {isin}.",
                    )
                    fail_count += 1
                    if fail_count >= MAX_FAIL_COUNT:
                        print(
                            f"Failed to retrieve stock prices {MAX_FAIL_COUNT} times in a row. Stopping monitoring."
                        )
                        send_email(
                            "Stock Alert: Service stopped due to repeated failures",
                            f"The service stopped after {MAX_FAIL_COUNT} consecutive failures to retrieve stock prices.",
                        )
                        return
            # Remove ISINs that have triggered alerts
            for entry in to_remove:
                active_alerts.remove(entry)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
