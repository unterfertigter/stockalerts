import requests
from bs4 import BeautifulSoup
import datetime
import pytz
from typing import Optional
import logging

logger = logging.getLogger("stock_monitor")


def get_tradegate_url(isin: str) -> str:
    return f"https://www.tradegate.de/orderbuch_umsaetze.php?isin={isin}"


def get_stock_price(isin: str, retries: int = 3, delay: int = 2) -> Optional[float]:
    url = get_tradegate_url(isin)
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            tbody = soup.find("tbody", {"id": "umsaetze_body"})
            if tbody:
                first_row = tbody.find("tr")
                if first_row:
                    cols = first_row.find_all("td")
                    if len(cols) >= 5:
                        price_text = (
                            cols[4].text.strip().replace("\xa0", "").replace(",", ".")
                        )
                        try:
                            return float(price_text)
                        except Exception:
                            logger.warning(f"Could not parse price: {price_text}")
            logger.warning("Could not find price on page.")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Error retrieving price for ISIN {isin} (attempt {attempt+1}/{retries}): {e}"
            )
            import time

            time.sleep(delay)
    logger.error(f"Failed to retrieve price for ISIN {isin} after {retries} attempts.")
    return None


def is_market_open() -> bool:
    now_cet = datetime.datetime.now(pytz.timezone("Europe/Berlin")).time()
    market_open = datetime.time(7, 30)
    market_close = datetime.time(22, 0)
    return market_open <= now_cet <= market_close
