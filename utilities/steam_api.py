import time
from datetime import datetime

import requests

from .file_helpers import load_dlc_cache, save_dlc_cache, save_library_cache

# --- Steam API Functions ---


def get_owned_games(api_key, steam_id):
    """Fetches the list of games owned by the specified Steam ID."""
    url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    params = {
        "key": api_key,
        "steamid": steam_id,
        "include_appinfo": 1,
        "include_played_free_games": 1,
        "format": "json",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Check for valid response structure
        if not data or "response" not in data or "games" not in data["response"]:
            # Added 0 for total_count to maintain consistency with the signature
            return (
                False,
                "Invalid response from Steam API. Check ID or profile privacy.",
                0,
            )

        games = data["response"].get("games", [])
        total_count = data["response"].get("game_count", len(games))

        # Filter for actual games (not just apps/tools) and sort by name
        games.sort(key=lambda x: x.get("name", "z").lower())

        return True, games, total_count

    except requests.exceptions.HTTPError as e:
        if response.status_code == 401 or response.status_code == 403:
            return False, "Access Denied. Check your Steam API Key.", 0
        if response.status_code == 400:
            return (
                False,
                "Bad Request. Check your Steam ID (it should be a 64-bit ID).",
                0,
            )
        return False, f"HTTP Error: {e}", 0
    except requests.exceptions.RequestException as e:
        return False, f"Network Error: {e}", 0
    except Exception as e:
        return False, f"An unexpected error occurred: {e}", 0


def get_app_details(appid):
    """Fetches store details for a single AppID, used primarily to find DLCs."""
    # This API uses the Steam Store, which is separate from the Web API, and is often rate-limited.
    url = "https://store.steampowered.com/api/appdetails"
    params = {
        "appids": appid,
        "cc": "us",  # country code for price/region filtering (US is standard)
        "filters": "dlc",  # We only care about the DLC list for now
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Check for successful response structure for the specific appid
        if data and str(appid) in data and data[str(appid)].get("success") is True:
            return True, data[str(appid)].get("data")

        return False, None

    except requests.exceptions.RequestException as e:
        # Network errors, timeouts, etc.
        print(f"Error fetching app details for {appid}: {e}")
        return False, None
    except Exception as e:
        # JSON errors, unexpected exceptions
        print(f"Unexpected error in get_app_details for {appid}: {e}")
        return False, None


def refresh_library_cache(config):
    """
    The main function to refresh the Steam library cache and update DLC information.

    Returns:
        tuple: (success: bool, message: str)
    """
    api_key = config.get("steam_api_key")
    steam_id = config.get("steam_id")

    if not api_key or not steam_id:
        return False, "API Key or Steam ID is missing from configuration."

    # 1. Fetch Owned Games
    success, result, total_count = get_owned_games(api_key, steam_id)

    if not success:
        return False, result  # 'result' contains the error message here

    # 2. Save Main Library Cache
    # The cache includes the list of games and a timestamp for when it was updated
    library_data = {
        "last_updated": int(datetime.now().timestamp()),
        "game_count": total_count,
        "games": result,
    }

    if not save_library_cache(library_data):
        return (
            False,
            "Successfully fetched data but failed to save the main library cache file.",
        )

    # 3. Fetch DLC Details for New Games
    # We fetch app details (which contains the DLC list) for games that don't have them yet.
    dlc_cache = load_dlc_cache()
    current_dlc_map = dlc_cache.get("dlc", {})

    # List of AppIDs that were successfully fetched for DLC
    fetched_appids = set(current_dlc_map.keys())

    games_to_check = [
        game for game in result if str(game["appid"]) not in fetched_appids
    ]

    # Limit DLC fetches to prevent hitting rate limits during a single refresh
    # We will only check 50 new games for DLC per refresh.
    dlc_fetch_count = 0
    for game in games_to_check[:50]:
        appid = str(game["appid"])
        success, details = get_app_details(appid)

        if success and details:
            # Check for DLC field and add to map if present
            if "dlc" in details and details["dlc"]:
                current_dlc_map[appid] = details["dlc"]
            else:
                # Store an empty list to avoid re-checking games with no DLC
                current_dlc_map[appid] = []
            dlc_fetch_count += 1
            # Add a small delay to respect Steam store API rate limits
            time.sleep(0.05)

    # 4. Save the updated DLC cache
    new_dlc_cache = {"dlc": current_dlc_map}
    if not save_dlc_cache(new_dlc_cache):
        # Log failure but don't fail the whole refresh, as the main library is updated
        print("Warning: Failed to save the updated DLC cache file.")

    final_message = f"Library refreshed successfully ({total_count} games). Checked {dlc_fetch_count} new games for DLC."
    return True, final_message
