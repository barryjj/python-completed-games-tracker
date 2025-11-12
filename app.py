import json
import os
import time
from datetime import datetime

import requests
from flask import \
    Blueprint  # Retained the import for completeness, though it's often imported locally in routes.
from flask import (Flask, flash, jsonify, redirect, render_template, request,
                   url_for)

# --- Import ONLY the necessary setup function from the new utilities package ---
from utilities.file_helpers import setup_files

# Initialize the Flask application
app = Flask(__name__)
# IMPORTANT: This secret key is needed for flash messages
app.secret_key = "a_super_secret_key_for_flash"


# --- Import and Register Blueprints (Existing Structure) ---
from routes.api import api_bp
from routes.views import views_bp

# Register the views blueprint for the root paths
app.register_blueprint(views_bp)
# Register the API blueprint with the /api prefix
app.register_blueprint(api_bp, url_prefix="/api")


if __name__ == "__main__":
    # Ensure all directories and files exist before the app starts
    setup_files()
    app.run(debug=True)
