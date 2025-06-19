import os
import time
import subprocess
import requests
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
import json

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))  # seconds
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_FROM = os.getenv("EMAIL_FROM")
CONFIG_PATH = os.getenv("CONFIG_PATH", "config.json")
MAX_FAIL_COUNT = int(os.getenv("MAX_FAIL_COUNT", "3"))

if not all([EMAIL_TO, EMAIL_FROM]):
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
    message = f"Subject: {subject}\nTo: {EMAIL_TO}\nFrom: {EMAIL_FROM}\n\n{body}"
    process = subprocess.Popen(['/usr/sbin/sendmail', '-t', '-oi'], stdin=subprocess.PIPE)
    process.communicate(message.encode('utf-8'))


def main():
    config = load_config(CONFIG_PATH)
    print(
        f"Checking {len(config)} ISIN(s) on Tradegate every {CHECK_INTERVAL} seconds."
    )
    # Track which ISINs have already triggered an alert
    active_entries = config.copy()
    # Fail count to track consecutive failures
    fail_count = 0
    while active_entries:
        to_remove = []
        for entry in active_entries:
            isin = entry["isin"]
            upper_threshold = entry.get("upper_threshold")
            lower_threshold = entry.get("lower_threshold")
            price = get_stock_price(isin)
            if price is not None:
                print(f"Current price for ISIN {isin}: {price}")
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
                    print(f"Alert sent for {isin} ({alert_reason}). Skipping this ISIN from now on.")
                    to_remove.append(entry)
            else:
                print(f"Failed to get stock price for {isin}.")
                send_email(
                    f"Stock Alert: Failed to retrieve price for {isin}",
                    f"The service failed to retrieve the stock price for ISIN {isin}.",
                )
                fail_count += 1
                if fail_count >= MAX_FAIL_COUNT:
                    print(
                        f"Failed to retrieve stock prices {MAX_FAIL_COUNT} times in a row. Stopping service."
                    )
                    send_email(
                        f"Stock Alert: Retrieval failed {MAX_FAIL_COUNT} times",
                        f"The service failed to retrieve stock prices {MAX_FAIL_COUNT} times in a row and is stopping.",
                    )
                    return
        # Remove ISINs that have triggered alerts
        for entry in to_remove:
            active_entries.remove(entry)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
