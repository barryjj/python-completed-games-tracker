import json
import os

# --- Configuration and File Paths ---
BASE_DIR = os.getcwd()

# Config File
CONFIG_DIR = os.path.join(BASE_DIR, "config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# Data Files
DATA_DIR = os.path.join(BASE_DIR, "data")
COMPLETED_FILE = os.path.join(
    DATA_DIR, "completed.json"
)  # Stores user's finished game log
LIBRARY_FILE = os.path.join(
    DATA_DIR, "library.json"
)  # Caches Steam owned games (main games)
DLC_FILE = os.path.join(DATA_DIR, "dlc.json")  # Caches DLC details per parent game

# --- File I/O Functions ---


def setup_files():
    """Ensures directories and default data files (config, library, completed log, dlc log) exist."""

    # 1. Ensure Config directory and file
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"steam_api_key": "", "steam_id": ""}, f, indent=4)

    # 2. Ensure Data directory
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    # 3. Ensure Library cache file
    if not os.path.exists(LIBRARY_FILE):
        with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
            json.dump({"games": [], "last_updated": 0}, f, indent=4)

    # 4. Ensure DLC cache file (structure: {"dlc": {"appid": [dlc_list]}})
    if not os.path.exists(DLC_FILE):
        with open(DLC_FILE, "w", encoding="utf-8") as f:
            json.dump({"dlc": {}}, f, indent=4)

    # 5. Ensure Completed log file
    if not os.path.exists(COMPLETED_FILE):
        with open(COMPLETED_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4)


def load_config():
    """Reads the steam API key and ID from the config file."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config_data):
    """Writes the steam API key and ID to the config file."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
        return True
    except Exception:
        return False


def load_library_cache():
    """Reads the cached list of owned games."""
    if not os.path.exists(LIBRARY_FILE):
        return {"games": [], "last_updated": 0}
    with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_library_cache(library_data):
    """Writes the list of owned games to the cache file."""
    try:
        with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
            json.dump(library_data, f, indent=4)
        return True
    except Exception:
        return False


def load_dlc_cache():
    """Reads the cached dictionary of DLCs (keyed by parent AppID)."""
    if not os.path.exists(DLC_FILE):
        return {"dlc": {}}
    with open(DLC_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_dlc_cache(dlc_data):
    """Writes the DLC data to the cache file."""
    try:
        with open(DLC_FILE, "w", encoding="utf-8") as f:
            json.dump(dlc_data, f, indent=4)
        return True
    except Exception:
        return False


def load_completed_log():
    """Reads the user's completed game log."""
    if not os.path.exists(COMPLETED_FILE):
        return []
    with open(COMPLETED_FILE, "r", encoding="utf-8") as f:
        # Load and handle case where file is empty or invalid JSON
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_completed_log(log_data):
    """Writes the user's completed game log."""
    try:
        with open(COMPLETED_FILE, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=4)
        return True
    except Exception:
        return False
