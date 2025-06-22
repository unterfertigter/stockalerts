import datetime
import logging
import time
from typing import Optional

import pytz
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("stock_monitor")


def get_tradegate_url(isin: str) -> str:
    """
    Construct the Tradegate URL for a given ISIN.
    """
    return f"https://www.tradegate.de/orderbuch_umsaetze.php?isin={isin}"


def get_stock_price(isin: str, retries: int = 3, delay: int = 30) -> Optional[float]:
    """
    Retrieve the latest stock price for a given ISIN from Tradegate.
    Retries up to `retries` times with `delay` seconds between attempts.
    Returns the price as float, or None if retrieval fails.
    """
    url = get_tradegate_url(isin)
    logger.info(f"Starting price retrieval for ISIN {isin} from {url}")
    for attempt in range(retries):
        try:
            logger.debug(f"Attempt {attempt + 1} to retrieve price for ISIN {isin} from {url}")
            response = requests.get(url, timeout=10)
            logger.debug(f"HTTP status code for ISIN {isin}: {response.status_code}")
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
                            price = float(price_text)
                            logger.info(f"Successfully retrieved price for ISIN {isin}: {price}")
                            return price
                        except ValueError:
                            logger.warning(f"Could not parse price for ISIN {isin}: {price_text}")
            logger.warning(f"Could not find price on page for ISIN {isin} (attempt {attempt + 1})")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving price for ISIN {isin} (attempt {attempt + 1}/{retries}): {e}")
        except Exception as e:
            logger.error(f"Unexpected exception while retrieving price for ISIN {isin}: {e}", exc_info=True)
        if attempt < retries - 1:
            logger.info(f"Retrying price retrieval for ISIN {isin} after {delay} seconds...")
            time.sleep(delay)
    logger.error(f"Failed to retrieve price for ISIN {isin} after {retries} attempts.")
    return None


def is_market_open(market_open: datetime.time, market_close: datetime.time) -> bool:
    """
    Returns True if the German market is open (Tradegate hours), else False.
    """
    now_cet = datetime.datetime.now(pytz.timezone("Europe/Berlin")).time()
    return market_open <= now_cet <= market_close
