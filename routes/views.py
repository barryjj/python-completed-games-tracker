from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, url_for

# --- Import Helpers from the Utilities Package ---
from utilities.file_helpers import (load_completed_log, load_config,
                                    load_library_cache)

# Initialize the Blueprint (Existing structure retained)
views_bp = Blueprint("views", __name__)


@views_bp.route("/")
def index_or_setup():
    """Checks config status and routes to index or setup page."""
    # 1. Load configuration using the utility function
    config = load_config()

    # 2. Check if the mandatory configuration is present
    if not config.get("steam_api_key") or not config.get("steam_id"):
        # Redirect to setup if credentials are missing
        flash("Please complete the setup to use the game tracker.", "warning")
        return redirect(url_for("views.setup"))

    # 3. If configuration exists, load data for the main dashboard
    library_cache = load_library_cache()

    last_updated_ts = library_cache.get("last_updated", 0)

    last_updated_display = "Never"
    if last_updated_ts:
        # Format the timestamp for display
        last_updated_display = datetime.fromtimestamp(last_updated_ts).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

    error_message = None
    if not library_cache.get("games"):
        error_message = (
            "Your game library is currently empty. "
            "Click 'Refresh Library' or check the Setup page."
        )

    return render_template(
        "index.html", last_updated=last_updated_display, error=error_message
    )


@views_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """Renders the setup page."""
    # Load existing config to pre-fill the form on GET request
    config = load_config()
    return render_template("setup.html", config=config)


@views_bp.route("/library")
def view_library():
    """Renders the full game library page."""
    config = load_config()
    if not config.get("steam_api_key") or not config.get("steam_id"):
        flash("Please complete the setup to view your library.", "warning")
        return redirect(url_for("views.setup"))

    # We don't fetch all games here, only render the container for the JS API call
    return render_template("library.html")


@views_bp.route("/log")
def view_log():
    """Renders the completed games log page."""
    config = load_config()
    if not config.get("steam_api_key") or not config.get("steam_id"):
        flash("Please complete the setup to view the completed log.", "warning")
        return redirect(url_for("views.setup"))

    # We don't fetch the log here, only render the container for the JS API call
    return render_template("log.html")
