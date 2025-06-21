import json
import threading
from typing import List, Dict


def load_config(path: str) -> List[Dict]:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Config file not found: {path}")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing config file '{path}': {e}")
        exit(1)


def save_config(path: str, config: list) -> None:
    with open(path, "w") as f:
        json.dump(config, f, indent=2)


# Thread-safe shared config
shared_config = []
config_lock = threading.Lock()
