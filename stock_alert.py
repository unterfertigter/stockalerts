from config_manager import load_config, save_config, shared_config, config_lock
from stock_monitor import get_stock_price, is_market_open
from email_utils import send_email
from flask import Flask, request, render_template, redirect, url_for, jsonify
import os
import datetime
import threading
from dotenv import load_dotenv
import logging

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

logging.basicConfig(
    format="[%(asctime)s] %(levelname)s: %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("stock_alert")

logger.info(f"CHECK_INTERVAL = {CHECK_INTERVAL}")
logger.info(f"EMAIL_FROM = {EMAIL_FROM}")
logger.info(f"EMAIL_TO = {EMAIL_TO}")
logger.info(f"SMTP_SERVER = {SMTP_SERVER}")
logger.info(f"SMTP_PORT = {SMTP_PORT}")
logger.info(f"SMTP_USERNAME = {SMTP_USERNAME}")
logger.info(f"SMTP_PASSWORD = {'***' if SMTP_PASSWORD else None}")
logger.info(f"CONFIG_PATH = {CONFIG_PATH}")
logger.info(f"MAX_FAIL_COUNT = {MAX_FAIL_COUNT}")

if not all(
    [EMAIL_TO, EMAIL_FROM, SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD]
):
    raise Exception("Missing required environment variables.")

# Flask app for admin UI
app = Flask(__name__)


@app.route("/", methods=["GET"])
def admin_page():
    with config_lock:
        config = list(shared_config)
    return render_template("admin.html", config=config)


@app.route("/update", methods=["POST"])
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


@app.route("/api/config", methods=["GET"])
def api_get_config():
    with config_lock:
        return jsonify(shared_config)


@app.route("/api/config", methods=["POST"])
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


def main():
    global shared_config
    config = load_config(CONFIG_PATH)
    # Ensure all entries have an 'active' field (default True)
    for entry in config:
        if "active" not in entry:
            entry["active"] = True
    with config_lock:
        shared_config[:] = config.copy()
    active_alerts = shared_config
    fail_count = 0
    logger.info(
        f"Monitoring {len(active_alerts)} ISIN(s) every {CHECK_INTERVAL} seconds. Max fail count: {MAX_FAIL_COUNT}"
    )
    while True:
        if is_market_open():
            to_deactivate = []
            with config_lock:
                alerts_to_check = [
                    entry for entry in shared_config if entry.get("active", True)
                ]
            if not alerts_to_check:
                logger.info(
                    "All entries are marked as inactive. No ISINs are currently being monitored."
                )
            for entry in alerts_to_check:
                isin = entry["isin"]
                upper_threshold = entry.get("upper_threshold")
                lower_threshold = entry.get("lower_threshold")
                price = get_stock_price(isin)
                if price is not None:
                    logger.info(f"Current price for ISIN {isin}: {price}")
                    fail_count = 0
                    alert = False
                    alert_reason = ""
                    if upper_threshold is not None and price >= upper_threshold:
                        alert = True
                        alert_reason = (
                            f"reached or exceeded upper threshold {upper_threshold}"
                        )
                    if lower_threshold is not None and price <= lower_threshold:
                        alert = True
                        alert_reason = (
                            f"reached or fell below lower threshold {lower_threshold}"
                        )
                    if alert:
                        send_email(
                            f"Stock Alert: {isin} {alert_reason} (price: {price})",
                            f"The stock with ISIN {isin} {alert_reason}. Current price: {price}.",
                            EMAIL_FROM,
                            EMAIL_TO,
                            SMTP_SERVER,
                            SMTP_PORT,
                            SMTP_USERNAME,
                            SMTP_PASSWORD,
                        )
                        logger.info(
                            f"Alert sent for {isin} ({alert_reason}). Marking as inactive."
                        )
                        to_deactivate.append(isin)
                else:
                    logger.warning(f"Failed to get stock price for ISIN {isin}.")
                    send_email(
                        f"Stock Alert: Failed to retrieve price for {isin}",
                        f"The service failed to retrieve the stock price for ISIN {isin}.",
                        EMAIL_FROM,
                        EMAIL_TO,
                        SMTP_SERVER,
                        SMTP_PORT,
                        SMTP_USERNAME,
                        SMTP_PASSWORD,
                    )
                    fail_count += 1
                    if fail_count >= MAX_FAIL_COUNT:
                        logger.error(
                            f"Failed to retrieve stock prices {MAX_FAIL_COUNT} times in a row. Stopping monitoring."
                        )
                        send_email(
                            "Stock Alert: Service stopped due to repeated failures",
                            f"The service stopped after {MAX_FAIL_COUNT} consecutive failures to retrieve stock prices.",
                            EMAIL_FROM,
                            EMAIL_TO,
                            SMTP_SERVER,
                            SMTP_PORT,
                            SMTP_USERNAME,
                            SMTP_PASSWORD,
                        )
                        return
            # Mark ISINs as inactive
            with config_lock:
                for entry in shared_config:
                    if entry["isin"] in to_deactivate:
                        entry["active"] = False
                alerts_to_check = [
                    entry for entry in shared_config if entry.get("active", True)
                ]
                if not alerts_to_check:
                    logger.info(
                        "All entries are marked as inactive. No ISINs are currently being monitored."
                    )
        import time

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    flask_thread = threading.Thread(
        target=lambda: app.run(
            host="0.0.0.0", port=5000, debug=False, use_reloader=False
        )
    )
    flask_thread.daemon = True
    flask_thread.start()
    main()
