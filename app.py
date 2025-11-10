"""
Flask application for a Steam game completion tracker.

This module handles configuration, local data management for the Steam library cache
and the user's completed game log, and interacts with the Steam Web API.
"""

import json
import os
import time

import requests
from flask import Flask, jsonify, redirect, render_template, request, url_for

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
LIBRARY_FILE = os.path.join(DATA_DIR, "library.json")  # Caches Steam owned games

# Initialize the Flask application
app = Flask(__name__)

# --- Helper Functions for File I/O ---


def setup_files():
    """Ensures directories and default data files (config, library, completed log) exist."""

    # 1. Ensure Config directory and file
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"steam_api_key": "", "steam_id": ""}, f, indent=4)

    # 2. Ensure Data directory
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    # 3. Ensure Completed Games Log file (default is empty list)
    if not os.path.exists(COMPLETED_FILE):
        with open(COMPLETED_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4)

    # 4. Ensure Steam Library Cache file (default includes last_updated)
    if not os.path.exists(LIBRARY_FILE):
        with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_updated": 0, "games": []}, f, indent=4)


def load_config():
    """Reads configuration data (keys) from the local JSON file."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"steam_api_key": "", "steam_id": ""}


def save_config(data):
    """Writes configuration data to the local JSON file."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return True
    except IOError as e:
        print(f"Error saving config: {e}")
        return False


# --- Data Load/Save Functions ---


def load_completed_log():
    """Reads the user's completed game log from the local JSON file."""
    try:
        with open(COMPLETED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_completed_log(data):
    """Writes the user's completed game log to the local JSON file."""
    try:
        with open(COMPLETED_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return True
    except IOError as e:
        print(f"Error saving completed log: {e}")
        return False


def load_library_cache():
    """Reads the cached Steam library from the local JSON file."""
    try:
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_updated": 0, "games": []}


def save_library_cache(games):
    """Writes the fetched Steam library to the local JSON file."""
    cache_data = {"last_updated": int(time.time()), "games": games}
    try:
        with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=4)
        return True
    except IOError as e:
        print(f"Error saving library cache: {e}")
        return False


# --- Steam API Interaction ---


def fetch_steam_library(config):
    """
    Fetches the list of games owned by a Steam user and caches it.
    Returns the list of games or None if an error occurs.
    """
    steam_id = config.get("steam_id")
    api_key = config.get("steam_api_key")

    if not api_key or not steam_id:
        return None

    # API endpoint to get owned games (includes playtime, game name, appid)
    url = "http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
    params = {
        "key": api_key,
        "steamid": steam_id,
        "format": "json",
        "include_appinfo": 1,  # Includes name and icon URL
        "include_played_free_games": 1,  # Include free games played
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        games = response.json().get("response", {}).get("games", [])
        save_library_cache(games)  # Cache the successful result
        return games
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching library for {steam_id}: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON decode error from API response: {e}")
        return None


# Run setup once before routes
setup_files()

# --- Flask Routes ---


@app.route("/")
def index_or_setup():
    """Checks for config validity, triggers library refresh, and directs to main page."""
    config = load_config()
    error = None

    if not config.get("steam_api_key") or not config.get("steam_id"):
        return redirect(url_for("setup"))

    library_cache = load_library_cache()

    # Check if cache is empty or older than 1 hour (3600 seconds)
    if not library_cache.get("games") or (
        time.time() - library_cache.get("last_updated", 0) > 3600
    ):
        print("Library cache is stale or empty. Attempting refresh...")
        games = fetch_steam_library(config)

        if games is None and library_cache.get("last_updated", 0) == 0:
            error = "Failed to refresh Steam library. Check API key/ID or connection."

    # Load the current state for rendering
    completed_log = load_completed_log()

    # Pass necessary data to the main view
    return render_template(
        "index.html",
        error=error,
        library_size=len(library_cache.get("games", [])),
        log_size=len(completed_log),
    )


@app.route("/setup", methods=["GET", "POST"])
def setup():
    """Handles the configuration setup form."""
    if request.method == "POST":
        api_key = request.form.get("steam_api_key", "").strip()
        steam_id = request.form.get("steam_id", "").strip()

        if not api_key or not steam_id:
            return render_template(
                "setup.html", error="Both Steam API Key and ID are required."
            )

        config_data = {"steam_api_key": api_key, "steam_id": steam_id}
        if save_config(config_data):
            # Clear library cache on new credentials to force a refresh
            save_library_cache({"last_updated": 0, "games": []})
            return redirect(url_for("index_or_setup"))

        return render_template("setup.html", error="Failed to save configuration file.")

    # GET request: Show setup form
    return render_template("setup.html", error=None)


@app.route("/log")
def log_dashboard():
    """Renders the main completed games log view."""
    return render_template("log.html")


@app.route("/api/library_search", methods=["GET"])
def library_search():
    """API endpoint to search the cached library for autocompletion."""
    query = request.args.get("q", "").lower()
    library = load_library_cache().get("games", [])

    # Filter the library based on the query, limit results for performance
    if query:
        results = [
            game["name"] for game in library if query in game.get("name", "").lower()
        ][:20]
    else:
        # Return a small sample if no query is given, mainly for form initialization
        results = [game["name"] for game in library][:10]

    return jsonify(results)


@app.route("/api/completed_log", methods=["GET", "POST"])
def handle_completed_log():
    """API endpoint to load (GET) or save (POST) the completed game log."""
    if request.method == "GET":
        log_data = load_completed_log()
        return jsonify(log_data)

    if request.method == "POST":
        try:
            # Expecting a single completed game object for addition
            new_entry = request.json
            if not new_entry or not isinstance(new_entry, dict):
                return (
                    jsonify(
                        {
                            "error": "Expected a valid JSON object for the new game entry."
                        }
                    ),
                    400,
                )

            log_data = load_completed_log()
            log_data.append(new_entry)

            if save_completed_log(log_data):
                return (
                    jsonify({"message": "Completed log entry added successfully"}),
                    201,
                )

            return jsonify({"error": "Failed to write data to file"}), 500

        except json.JSONDecodeError:
            return jsonify({"error": "Invalid JSON data submitted"}), 400
        except Exception as e:
            return jsonify({"error": f"Internal server error: {e}"}), 500

    return jsonify({"error": "Method not allowed"}), 405


@app.route("/api/library_status", methods=["GET"])
def library_status():
    """API endpoint to check the status of the local library cache."""
    library_cache = load_library_cache()

    # Calculate time since last update
    last_updated_ts = library_cache.get("last_updated", 0)
    time_since = int(time.time() - last_updated_ts) if last_updated_ts else None

    return jsonify(
        {
            "size": len(library_cache.get("games", [])),
            "last_updated": last_updated_ts,
            "time_since_last_update": time_since,
            "games_sample": library_cache.get("games", [])[
                :5
            ],  # Send a sample for check
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
