import json
import logging
import threading
from typing import Dict, List

logger = logging.getLogger("config_manager")


def load_config(path: str) -> List[Dict]:
    """
    Load the configuration from a JSON file at the given path.
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


def save_config(path: str, config: List[Dict]) -> None:
    """
    Save the configuration to a JSON file at the given path.
    Logs the number of ISINs saved.
    """
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    logger.info(f"Saved config to {path} with {len(config)} ISIN(s)")


# Thread-safe shared config
shared_config: List[Dict] = []
config_lock = threading.Lock()
