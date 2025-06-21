import json
import logging
import threading
from typing import Dict, List

logger = logging.getLogger("config_manager")


def load_config(path: str) -> List[Dict]:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Config file not found: {path}")
        exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing config file '{path}': {e}")
        exit(1)


def save_config(path: str, config: list) -> None:
    with open(path, "w") as f:
        json.dump(config, f, indent=2)


# Thread-safe shared config
shared_config = []
config_lock = threading.Lock()
