import os
import sys
import json
import csv
import secrets
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, request, session
import requests

# Add parent directory to path so we can import from the root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the original app
from tracker import app as flask_app

# Create the app instance
app = flask_app

# Set Flask secret key from environment variable if available
if 'FLASK_SECRET_KEY' in os.environ:
    app.secret_key = os.environ.get('FLASK_SECRET_KEY')

# For Vercel, we need to make sure the CSV and config files are in a writable location
if 'VERCEL' in os.environ:
    # Use /tmp directory on Vercel for writable files
    CONFIG_FILE = '/tmp/config.json'
    CSV_FILE = '/tmp/mentions_metadata.csv'
    SAVE_FOLDER = '/tmp/mentions'
    
    # Update the global variables in the original module
    import tracker
    tracker.CONFIG_FILE = CONFIG_FILE
    tracker.CSV_FILE = CSV_FILE
    tracker.SAVE_FOLDER = SAVE_FOLDER
    
    # Ensure directories exist
    os.makedirs(SAVE_FOLDER, exist_ok=True)
    
    # Initialize CSV if it doesn't exist
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['username', 'timestamp', 'media_type', 'filename'])
    
    # Initialize config if it doesn't exist
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            'app_id': os.environ.get('INSTAGRAM_APP_ID', ''),
            'app_secret': os.environ.get('INSTAGRAM_APP_SECRET', ''),
            'redirect_uri': os.environ.get('REDIRECT_URI', ''),
            'access_token': os.environ.get('INSTAGRAM_ACCESS_TOKEN', ''),
            'ig_user_id': os.environ.get('INSTAGRAM_USER_ID', ''),
            'check_interval': int(os.environ.get('CHECK_INTERVAL', 3600))
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=4)

# Background worker doesn't work in serverless environments
# We'll need to use a scheduled function or external service for this in production

# For Vercel serverless environment
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')
else:
    # This is the handler that Vercel uses
    from werkzeug.middleware.dispatcher import DispatcherMiddleware
    from werkzeug.exceptions import NotFound
    
    app.wsgi_app = DispatcherMiddleware(NotFound(), {'/': app.wsgi_app})
    
    # Export the app variable for Vercel
    application = app 