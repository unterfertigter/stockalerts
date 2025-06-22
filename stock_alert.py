import datetime
import logging
import os
import signal
import sys
import threading
import time  # Added back to ensure time.sleep works
import traceback

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for

from config_manager import config_lock, load_config, save_config, shared_config
from email_utils import send_email, set_email_config
from stock_monitor import get_stock_price, is_market_open

# Load environment variables from .env file
load_dotenv()

# Configuration constants from environment variables
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))  # seconds between stock checks
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
CONFIG_PATH = os.getenv("CONFIG_PATH", "config.json")
MAX_FAIL_COUNT = int(os.getenv("MAX_FAIL_COUNT", "3"))
MAX_EXCEPTIONS = int(os.getenv("MAX_EXCEPTIONS", "10"))

# Load market open/close times from environment variables, defaulting to 07:30 and 22:00
MARKET_OPEN_STR = os.getenv("MARKET_OPEN", "07:30")
MARKET_CLOSE_STR = os.getenv("MARKET_CLOSE", "22:00")
MARKET_OPEN = datetime.datetime.strptime(MARKET_OPEN_STR, "%H:%M").time()
MARKET_CLOSE = datetime.datetime.strptime(MARKET_CLOSE_STR, "%H:%M").time()

# Set up logging for the application
logging.basicConfig(
    format="[%(asctime)s] %(levelname)s: %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("stock_alert")

# Log configuration for debugging
logger.info(f"CHECK_INTERVAL = {CHECK_INTERVAL}")
logger.info(f"EMAIL_FROM = {EMAIL_FROM}")
logger.info(f"EMAIL_TO = {EMAIL_TO}")
logger.info(f"SMTP_SERVER = {SMTP_SERVER}")
logger.info(f"SMTP_PORT = {SMTP_PORT}")
logger.info(f"SMTP_USERNAME = {SMTP_USERNAME}")
logger.info(f"SMTP_PASSWORD = {'***' if SMTP_PASSWORD else None}")
logger.info(f"CONFIG_PATH = {CONFIG_PATH}")
logger.info(f"MAX_FAIL_COUNT = {MAX_FAIL_COUNT}")
logger.info(f"MAX_EXCEPTIONS = {MAX_EXCEPTIONS}")
logger.info(f"MARKET_OPEN = {MARKET_OPEN}")
logger.info(f"MARKET_CLOSE = {MARKET_CLOSE}")

# Ensure all required environment variables are set
if not all([EMAIL_TO, EMAIL_FROM, SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD]):
    raise Exception("Missing required environment variables.")

# Initialize Flask app for admin UI
app = Flask(__name__)

shutdown_event = threading.Event()


@app.route("/", methods=["GET"])
def admin_page():
    # Render the admin UI with the current config
    with config_lock:
        config = list(shared_config)
    return render_template("admin.html", config=config)


@app.route("/update", methods=["POST"])
def update_threshold():
    # Handle updates to thresholds and active status from the admin UI
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
    logger.info(f"Config updated via admin UI for ISIN {isin}: upper={upper}, lower={lower}, active={active}")
    return redirect(url_for("admin_page"))


@app.route("/api/config", methods=["GET"])
def api_get_config():
    # API endpoint to get the current config as JSON
    with config_lock:
        return jsonify(shared_config)


@app.route("/api/config", methods=["POST"])
def api_update_config():
    # API endpoint to update thresholds for a given ISIN
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
    logger.info(f"Config updated via API for ISIN {isin}: upper={upper}, lower={lower}")
    return {"status": "ok"}


def handle_shutdown(signum, frame):
    logger.info(f"Received shutdown signal ({signum}). Shutting down gracefully...")
    shutdown_event.set()


# Register signal handlers
signal.signal(signal.SIGINT, handle_shutdown)  # Ctrl+C
signal.signal(signal.SIGTERM, handle_shutdown)  # Docker/K8s


def main():
    """Main monitoring loop: checks stock prices, sends alerts, and manages config state."""
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
    # Initial market state check and log
    market_now = is_market_open(MARKET_OPEN, MARKET_CLOSE)
    if market_now:
        logger.info("Market is currently open. Monitoring of stock prices is active.")
    else:
        logger.info("Market is currently closed. Stock price monitoring is paused until next market open.")
    last_market_open = market_now

    exception_count = 0  # Track consecutive unexpected exceptions

    while not shutdown_event.is_set():
        try:
            # Check if the market is currently open
            market_now = is_market_open(MARKET_OPEN, MARKET_CLOSE)
            # Log only on market open/close transitions
            if last_market_open is not None and market_now != last_market_open:
                if market_now:
                    logger.info("Market has just opened. Continuing to monitor stock prices.")
                else:
                    logger.info("Market has just closed. Pausing stock price monitoring until next market open.")
            last_market_open = market_now
            if market_now:
                to_deactivate = []  # List of ISINs to deactivate after alerting
                with config_lock:
                    alerts_to_check = [entry for entry in shared_config if entry.get("active", True)]
                if not alerts_to_check:
                    logger.info("All entries are marked as inactive. No ISINs are currently being monitored.")
                for entry in alerts_to_check:
                    isin = entry["isin"]
                    upper_threshold = entry.get("upper_threshold")
                    lower_threshold = entry.get("lower_threshold")
                    price = get_stock_price(isin)
                    if price is not None:
                        logger.info(f"Current price for ISIN {isin}: {price}")
                        fail_count = 0  # Reset fail count on success
                        alert = False
                        alert_reason = ""
                        # Check if price crosses upper threshold
                        if upper_threshold is not None and price >= upper_threshold:
                            alert = True
                            alert_reason = f"reached or exceeded upper threshold {upper_threshold}"
                        # Check if price crosses lower threshold
                        if lower_threshold is not None and price <= lower_threshold:
                            alert = True
                            alert_reason = f"reached or fell below lower threshold {lower_threshold}"
                        if alert:
                            logger.info(f"Sending alert email for ISIN {isin}: {alert_reason}")
                            send_email(
                                f"Stock Alert: {isin} {alert_reason} (price: {price})",
                                f"The stock with ISIN {isin} {alert_reason}. Current price: {price}.",
                            )
                            logger.info(f"Alert sent for {isin} ({alert_reason}). Marking as inactive.")
                            to_deactivate.append(isin)
                            logger.info(f"ISIN {isin} marked as inactive after alert.")
                    else:
                        # Failed to get price: log and increment fail count
                        logger.warning(f"Failed to get stock price for ISIN {isin}.")
                        fail_count += 1
                        logger.warning(f"Incremented fail_count to {fail_count}")
                        # If too many consecutive failures, stop monitoring and notify
                        if fail_count >= MAX_FAIL_COUNT:
                            logger.error(
                                f"Failed to retrieve stock prices {MAX_FAIL_COUNT} times in a row. Stopping monitoring."
                            )
                            logger.info("Sending service stopped notification email.")
                            send_email(
                                "Stock Alert: Service terminated due to repeated failures",
                                f"The service terminated after {MAX_FAIL_COUNT} consecutive failures to retrieve stock prices.",
                            )
                            return
                # Mark ISINs as inactive after alerting
                with config_lock:
                    for entry in shared_config:
                        if entry["isin"] in to_deactivate:
                            entry["active"] = False
                            logger.info(f"ISIN {entry['isin']} set to inactive in config.")
                    alerts_to_check = [entry for entry in shared_config if entry.get("active", True)]
                    if not alerts_to_check:
                        logger.info("All entries are marked as inactive. No ISINs are currently being monitored.")
            # Wait before next check
            time.sleep(CHECK_INTERVAL)
            exception_count = 0  # Reset exception count after successful loop
        except Exception as e:
            # Catch-all for unexpected errors in the main loop
            exception_count += 1

            logger.error(
                f"Unexpected exception in main monitoring loop (consecutive count: {exception_count}): {e}",
                exc_info=True,
            )
            if exception_count >= MAX_EXCEPTIONS:
                logger.critical(f"Terminating service after {MAX_EXCEPTIONS} consecutive unexpected exceptions.")
                exc_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
                send_email(
                    "Stock Alert: Service terminated due to repeated unexpected exceptions",
                    f"The service terminated after {MAX_EXCEPTIONS} consecutive unexpected exceptions in the main loop.\n\n"
                    + "Last exception:\n"
                    + exc_str,
                )
                break
            time.sleep(CHECK_INTERVAL)
    # After loop exits, do cleanup
    with config_lock:
        save_config(CONFIG_PATH, shared_config)
    logger.info("Service shutdown complete.")
    # Optionally:
    # send_email("Stock Alert: Service stopped", "The service was stopped gracefully.")


if __name__ == "__main__":
    # Set up email config once at startup
    set_email_config(
        EMAIL_FROM,
        EMAIL_TO,
        SMTP_SERVER,
        SMTP_PORT,
        SMTP_USERNAME,
        SMTP_PASSWORD,
    )
    # Start Flask admin UI in a separate thread
    flask_thread = threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()
    # Start the main monitoring loop
    main()
