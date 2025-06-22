import json
import logging
import os
import threading
from typing import Dict, List

logger = logging.getLogger(__name__)

CONFIG_PATH = os.getenv("CONFIG_PATH", "config.json")


def load_config(path: str = CONFIG_PATH) -> List[Dict]:
    """
    Load the configuration from a JSON file at the given path (defaults to CONFIG_PATH).
    Returns a list of ISIN config dicts.
    Logs the number of ISINs loaded.
    """
    try:
        with open(path, "r") as f:
            config = json.load(f)
            logger.info(f"Loaded config from {path} with {len(config)} ISIN(s)")
            return config
    except FileNotFoundError:
        logger.error(f"Config file not found: {path}")
        exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing config file '{path}': {e}")
        exit(1)


def save_config(config: List[Dict], path: str = CONFIG_PATH) -> None:
    """
    Save the configuration to a JSON file at the given path (defaults to CONFIG_PATH).
    Logs the number of ISINs saved.
    """
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    logger.info(f"Saved config to {path} with {len(config)} ISIN(s)")


# Thread-safe shared config
shared_config: List[Dict] = []
config_lock = threading.Lock()
