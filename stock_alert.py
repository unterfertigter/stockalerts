from email.mime.text import MIMEText
import os
import time
import requests
from bs4 import BeautifulSoup
import json
import datetime
import smtplib
import pytz
import threading
from flask import Flask, request, render_template_string, redirect, url_for, jsonify
from dotenv import load_dotenv

load_dotenv()

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))  # seconds
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
CONFIG_PATH = os.getenv("CONFIG_PATH", "config.json")
MAX_FAIL_COUNT = int(os.getenv("MAX_FAIL_COUNT", "3"))

def log(msg):
    print(f"[{datetime.datetime.now().isoformat(sep=' ', timespec='seconds')}] {msg}")

log(f"CHECK_INTERVAL = {CHECK_INTERVAL}")
log(f"EMAIL_FROM = {EMAIL_FROM}")
log(f"EMAIL_TO = {EMAIL_TO}")
log(f"SMTP_SERVER = {SMTP_SERVER}")
log(f"SMTP_PORT = {SMTP_PORT}")
log(f"SMTP_USERNAME = {SMTP_USERNAME}")
log(f"SMTP_PASSWORD = {'***' if SMTP_PASSWORD else None}")
log(f"CONFIG_PATH = {CONFIG_PATH}")
log(f"MAX_FAIL_COUNT = {MAX_FAIL_COUNT}")

if not all([EMAIL_TO, EMAIL_FROM, SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD]):
    raise Exception("Missing required environment variables.")


def load_config(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        log(f"Config file not found: {path}")
        exit(1)
    except json.JSONDecodeError as e:
        log(f"Error parsing config file '{path}': {e}")
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
                    log("Could not parse price:", price_text)
    log("Could not find price on page.")
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


# Shared config and lock for thread safety
shared_config = []
config_lock = threading.Lock()

# Flask app for admin UI
app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head><title>Stock Alert Admin</title></head>
<body>
<h2>Stock Alert Administration</h2>
<table border="1">
<tr><th>ISIN</th><th>Upper Threshold</th><th>Lower Threshold</th><th>Active</th><th>Actions</th></tr>
{% for entry in config %}
<tr>
  <form method="post" action="/update">
    <td>{{ entry['isin'] }}</td>
    <td><input type="number" step="any" name="upper_threshold" value="{{ entry.get('upper_threshold', '') }}"></td>
    <td><input type="number" step="any" name="lower_threshold" value="{{ entry.get('lower_threshold', '') }}"></td>
    <td><input type="checkbox" name="active" value="1" {% if entry.get('active', True) %}checked{% endif %}></td>
    <td>
      <input type="hidden" name="isin" value="{{ entry['isin'] }}">
      <input type="submit" value="Update">
    </td>
  </form>
</tr>
{% endfor %}
</table>
</body>
</html>
'''

# --- Flask admin UI and API endpoints ---

@app.route("/", methods=["GET"])
# Renders the main admin web page with a table of all ISINs and their thresholds, allowing editing via a form.
def admin_page():
    with config_lock:
        config = list(shared_config)
    return render_template_string(HTML_TEMPLATE, config=config)

@app.route("/update", methods=["POST"])
# Handles form submissions from the admin page to update thresholds for a specific ISIN and its active status.
def update_threshold():
    isin = request.form["isin"]
    upper = request.form.get("upper_threshold")
    lower = request.form.get("lower_threshold")
    active = request.form.get("active") == "1"
    with config_lock:
        for entry in shared_config:
            if entry["isin"] == isin:
                entry["upper_threshold"] = float(upper) if upper else None
                entry["lower_threshold"] = float(lower) if lower else None
                entry["active"] = active
        save_config(CONFIG_PATH, shared_config)
    return redirect(url_for("admin_page"))

@app.route("/C", methods=["GET"])
# Returns the current alert configuration as JSON (for API clients or debugging).
def api_get_config():
    with config_lock:
        return jsonify(shared_config)

@app.route("/api/config", methods=["POST"])
# Allows updating thresholds for a specific ISIN via a JSON API (for programmatic access).
def api_update_config():
    data = request.json
    isin = data.get("isin")
    upper = data.get("upper_threshold")
    lower = data.get("lower_threshold")
    with config_lock:
        for entry in shared_config:
            if entry["isin"] == isin:
                entry["upper_threshold"] = upper
                entry["lower_threshold"] = lower
        save_config(CONFIG_PATH, shared_config)
    return {"status": "ok"}


def save_config(path: str, config: list) -> None:
    with open(path, "w") as f:
        json.dump(config, f, indent=2)


def main():
    global shared_config
    config = load_config(CONFIG_PATH)
    # Ensure all entries have an 'active' field (default True)
    for entry in config:
        if "active" not in entry:
            entry["active"] = True
    with config_lock:
        shared_config = config.copy()
    active_alerts = shared_config
    
    # Fail count to track consecutive failures
    fail_count = 0

    log(f"Monitoring {len(active_alerts)} ISIN(s) every {CHECK_INTERVAL} seconds. Max fail count: {MAX_FAIL_COUNT}")

    market_open = datetime.time(7, 30)
    market_close = datetime.time(22, 0)

    while True:
        now_cet = datetime.datetime.now(pytz.timezone("Europe/Berlin")).time()
        if market_open <= now_cet <= market_close:
            to_deactivate = []
            with config_lock:
                alerts_to_check = [entry for entry in shared_config if entry.get("active", True)]
            if not alerts_to_check:
                log("All entries are marked as inactive. No ISINs are currently being monitored.")
            for entry in alerts_to_check:
                isin = entry["isin"]
                upper_threshold = entry.get("upper_threshold")
                lower_threshold = entry.get("lower_threshold")
                price = get_stock_price(isin)
                if price is not None:
                    log(f"Current price for ISIN {isin}: {price}")
                    fail_count = 0
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
                        log(f"Alert sent for {isin} ({alert_reason}). Marking as inactive.")
                        to_deactivate.append(isin)
                else:
                    log(f"Failed to get stock price for ISIN {isin}.")
                    send_email(
                        f"Stock Alert: Failed to retrieve price for {isin}",
                        f"The service failed to retrieve the stock price for ISIN {isin}.",
                    )
                    fail_count += 1
                    if fail_count >= MAX_FAIL_COUNT:
                        log(
                            f"Failed to retrieve stock prices {MAX_FAIL_COUNT} times in a row. Stopping monitoring."
                        )
                        send_email(
                            "Stock Alert: Service stopped due to repeated failures",
                            f"The service stopped after {MAX_FAIL_COUNT} consecutive failures to retrieve stock prices.",
                        )
                        return
            # Mark ISINs as inactive
            with config_lock:
                for entry in shared_config:
                    if entry["isin"] in to_deactivate:
                        entry["active"] = False
                alerts_to_check = [entry for entry in shared_config if entry.get("active", True)]
                if not alerts_to_check:
                    log("All entries are marked as inactive. No ISINs are currently being monitored.")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    # Start Flask app in a separate thread
    flask_thread = threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()
    main()
