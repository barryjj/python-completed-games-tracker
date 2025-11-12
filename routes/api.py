import json
import time
import uuid
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

# --- Import Helpers from the Utilities Package ---
# File I/O helpers
from utilities.file_helpers import (load_completed_log, load_config,
                                    load_dlc_cache, load_library_cache,
                                    save_completed_log, save_config)
# Steam API and refresh logic
from utilities.steam_api import refresh_library_cache

# Initialize the Blueprint (Existing structure retained)
api_bp = Blueprint("api", __name__)


@api_bp.route("/setup", methods=["POST"])
def api_setup_post():
    """
    Handles the POST request for setup:
    saves credentials and verifies them by attempting a library refresh.
    """
    try:
        data = request.get_json()
        api_key = data.get("steam_api_key", "").strip()
        steam_id = data.get("steam_id", "").strip()

        if not api_key or not steam_id:
            return (
                jsonify({"error": "Both Steam API Key and Steam ID are required."}),
                400,
            )

        config_data = {"steam_api_key": api_key, "steam_id": steam_id}
        save_config(config_data)

        # Execute the refresh logic from utilities/steam_api.py
        success, message = refresh_library_cache(config_data)

        if success:
            return jsonify(
                {
                    "message": f"Credentials verified and saved! {message} Redirecting...",
                    "success": True,
                }
            )
        else:
            # If refresh failed, save the credentials but report the error
            return (
                jsonify(
                    {"error": f"Credentials saved, but verification failed: {message}"}
                ),
                200,  # Still return 200 since credentials were saved
            )

    except Exception as e:
        return (
            jsonify({"error": f"An unexpected error occurred during setup: {str(e)}"}),
            500,
        )


@api_bp.route("/refresh", methods=["POST"])
def api_refresh_library():
    """Triggers the refresh of the Steam library cache."""
    try:
        config = load_config()
        if not config.get("steam_api_key") or not config.get("steam_id"):
            return (
                jsonify({"error": "Setup required (missing Steam API Key or ID)."}),
                400,
            )

        # Run the refresh logic
        success, message = refresh_library_cache(config)

        if success:
            return jsonify({"message": f"Library refresh successful! {message}"})
        else:
            return jsonify({"error": f"Library refresh failed: {message}"}), 500

    except Exception as e:
        current_app.logger.error(f"Error during library refresh: {e}")
        return (
            jsonify({"error": f"An internal error occurred during refresh: {str(e)}"}),
            500,
        )


# **FIX: Renamed the function and endpoint to api_library_status to match index.html**
@api_bp.route("/library/status", methods=["GET"])
def api_library_status():
    """
    Returns high-level statistics about the cached library for the dashboard.
    Resolves the BuildError by matching the name expected by url_for.
    """
    try:
        library_cache = load_library_cache()

        games = library_cache.get("games", [])
        total_games = len(games)

        # Calculate total playtime
        total_playtime_minutes = sum(game.get("playtime_forever", 0) for game in games)

        # Format the last updated timestamp
        last_updated_ts = library_cache.get("last_updated", 0)
        last_updated_display = "Never"
        if last_updated_ts:
            last_updated_display = datetime.fromtimestamp(last_updated_ts).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )

        return jsonify(
            {
                "total_games": total_games,
                "total_playtime_minutes": total_playtime_minutes,
                "last_updated": last_updated_display,
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error fetching library status: {e}")
        return jsonify({"error": f"Failed to retrieve library status: {str(e)}"}), 500


@api_bp.route("/library/stats", methods=["GET"])
def api_completion_stats():
    """
    Returns completion statistics for the dashboard.
    """
    try:
        library_cache = load_library_cache()
        completed_log = load_completed_log()

        games = library_cache.get("games", [])
        total_games = len(games)

        completed_appids = {
            entry["appid"] for entry in completed_log if entry.get("appid")
        }

        # Count main games that are marked as completed
        completed_count = sum(
            1 for game in games if str(game.get("appid")) in completed_appids
        )

        return jsonify({"total_games": total_games, "completed_count": completed_count})

    except Exception as e:
        current_app.logger.error(f"Error fetching completion stats: {e}")
        return jsonify({"error": f"Failed to retrieve completion stats: {str(e)}"}), 500


@api_bp.route("/library", methods=["GET"])
def api_get_library():
    """Returns the full cached game library, including completion status."""
    try:
        library_cache = load_library_cache()
        completed_log = load_completed_log()

        games = library_cache.get("games", [])

        # Map completed entries by appid for fast lookup
        completed_appids = {
            entry["appid"] for entry in completed_log if entry.get("appid")
        }

        # Combine library data with completion status
        result = []
        for game in games:
            # Ensure appid is treated as a string for comparison
            appid_str = str(game.get("appid"))
            game_data = {
                "appid": appid_str,
                "name": game.get("name", "Unknown Game"),
                "playtime_forever": game.get("playtime_forever", 0),
                "is_completed": appid_str in completed_appids,
            }
            result.append(game_data)

        return jsonify({"games": result})

    except Exception as e:
        current_app.logger.error(f"Error fetching full library: {e}")
        return jsonify({"error": f"Failed to retrieve game library: {str(e)}"}), 500


@api_bp.route("/log", methods=["POST"])
def api_log_completion():
    """Adds a new entry to the completed game log."""
    try:
        data = request.get_json()

        # Basic validation
        if not data.get("game_name") or not data.get("appid"):
            return jsonify({"error": "Missing game name or AppID."}), 400

        # Load existing log
        log = load_completed_log()

        # Check for duplicates (same AppID can only be logged once as a main completion)
        if any(entry.get("appid") == data["appid"] for entry in log):
            return (
                jsonify(
                    {
                        "error": f"Game with AppID {data['appid']} is already in the completed log."
                    }
                ),
                409,
            )

        # Prepare new log entry
        new_entry = {
            "id": str(uuid.uuid4()),  # Unique ID for easier deletion
            "appid": str(data["appid"]),
            "game_name": data["game_name"],
            "completion_date": data.get(
                "completion_date", datetime.now().strftime("%Y-%m-%d")
            ),
            "is_dlc_expansion": data.get("is_dlc_expansion", False),
            "notes": data.get("notes", ""),
            "collection_name": data.get("collection_name", None),
            "logged_at": datetime.now().isoformat(),
        }

        log.append(new_entry)
        save_completed_log(log)

        return (
            jsonify(
                {"message": "Completion logged successfully.", "id": new_entry["id"]}
            ),
            201,
        )

    except Exception as e:
        current_app.logger.error(f"Error logging completion: {e}")
        return (
            jsonify(
                {
                    "error": f"An internal error occurred while logging completion: {str(e)}"
                }
            ),
            500,
        )


@api_bp.route("/log/<log_id>", methods=["DELETE"])
def api_delete_log_entry(log_id):
    """Deletes a single entry from the completed game log by ID."""
    try:
        log = load_completed_log()

        initial_length = len(log)
        # Filter out the entry with the matching ID
        new_log = [entry for entry in log if entry.get("id") != log_id]

        if len(new_log) == initial_length:
            return jsonify({"error": "Log entry not found."}), 404

        save_completed_log(new_log)

        return jsonify({"message": "Log entry deleted successfully."}), 200

    except Exception as e:
        current_app.logger.error(f"Error deleting log entry: {e}")
        return (
            jsonify(
                {
                    "error": f"An internal error occurred while deleting log entry: {str(e)}"
                }
            ),
            500,
        )


@api_bp.route("/log", methods=["GET"])
def api_get_log():
    """Returns the entire completed game log."""
    try:
        log = load_completed_log()
        # Ensure log is sorted by completion date descending (most recent first)
        log.sort(key=lambda x: x.get("completion_date", "1900-01-01"), reverse=True)
        return jsonify({"log": log})

    except Exception as e:
        current_app.logger.error(f"Error fetching log: {e}")
        return jsonify({"error": f"Failed to retrieve log: {str(e)}"}), 500


@api_bp.route("/search_games", methods=["GET"])
def api_search_games():
    """
    Searches the cached library for main games or DLCs based on a query.
    """
    query = request.args.get("query", "").lower().strip()
    search_type = request.args.get("type", "game")
    parent_appid = request.args.get("parent_appid")

    library_cache = load_library_cache()
    dlc_cache = load_dlc_cache()

    if not query or len(query) < 2:
        return jsonify({"results": []})

    results = []

    if search_type == "game":
        # Search main games
        results = [
            {"appid": game["appid"], "name": game["name"]}
            for game in library_cache.get("games", [])
            if isinstance(game, dict)
            and "appid" in game
            and query in game.get("name", "").lower()
        ]

    elif search_type == "dlc":
        # Search cached DLCs based on parent_appid
        if parent_appid and parent_appid in dlc_cache.get("dlc", {}):
            dlc_list = dlc_cache["dlc"][parent_appid]

            # Filter DLC list by the name search query
            results = [
                {"appid": item["appid"], "name": item["description"]}
                for item in dlc_list
                if "appid" in item and query in item.get("description", "").lower()
            ]

    return jsonify({"results": results})
