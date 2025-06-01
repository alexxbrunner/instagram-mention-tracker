import requests
import os
import csv
import json
import secrets
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, request, session
import threading
import time
import urllib.parse

# === CONFIGURATION ===
CONFIG_FILE = 'config.json'
SAVE_FOLDER = 'static/mentions'
CSV_FILE = 'mentions_metadata.csv'
CHECK_INTERVAL = 3600  # Check for new mentions every hour (in seconds)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# === Ensure directories exist ===
os.makedirs(SAVE_FOLDER, exist_ok=True)
os.makedirs('templates', exist_ok=True)
os.makedirs('static', exist_ok=True)

# === Load Config ===
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        'app_id': '',
        'app_secret': '',
        'redirect_uri': '',
        'access_token': '',
        'ig_user_id': '',
        'check_interval': CHECK_INTERVAL
    }

# === Save Config ===
def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# Load configuration
config = load_config()
ACCESS_TOKEN = config.get('access_token', '')
IG_USER_ID = config.get('ig_user_id', '')
CHECK_INTERVAL = config.get('check_interval', CHECK_INTERVAL)

# === CSV Setup ===
def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['username', 'timestamp', 'media_type', 'filename'])

# === Download media file ===
def download_media(media_url, media_type):
    extension = 'jpg' if media_type == 'IMAGE' else 'mp4'
    filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{extension}"
    filepath = os.path.join(SAVE_FOLDER, filename)

    response = requests.get(media_url)
    if response.status_code == 200:
        with open(filepath, 'wb') as f:
            f.write(response.content)
        return filename
    else:
        print(f"Failed to download media: {media_url}")
        return None

# === Save metadata to CSV ===
def save_to_csv(username, timestamp, media_type, filename):
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([username, timestamp, media_type, filename])

# === Fetch mentioned media ===
def fetch_mentions():
    if not ACCESS_TOKEN or not IG_USER_ID:
        print("Missing Instagram credentials. Please configure them first.")
        return 0

    # Get user's media where they might be tagged/mentioned
    url = f"https://graph.instagram.com/me/media"
    params = {
        'access_token': ACCESS_TOKEN,
        'fields': 'id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,username',
        'limit': 50
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json().get('data', [])
        print(f"Found {len(data)} media posts")
        
        new_mentions = 0
        for item in data:
            username = item.get('username', 'unknown')
            timestamp = item.get('timestamp')
            media_type = item.get('media_type')
            media_url = item.get('media_url')
            
            # For video, use thumbnail if media_url is not available
            if media_type == 'VIDEO' and not media_url:
                media_url = item.get('thumbnail_url')
    
            if not media_url:
                continue
    
            filename = download_media(media_url, media_type)
            if filename:
                save_to_csv(username, timestamp, media_type, filename)
                new_mentions += 1
                
        return new_mentions
        
    except Exception as e:
        print(f"Error fetching mentions: {str(e)}")
        return 0

# === Load mentions data ===
def get_mentions():
    if not os.path.exists(CSV_FILE):
        return []
    
    mentions = []
    with open(CSV_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            mentions.append(row)
    
    # Sort by timestamp (most recent first)
    mentions.sort(key=lambda x: x['timestamp'], reverse=True)
    return mentions

# === Get user info from Instagram ===
def get_instagram_user_info(access_token):
    url = "https://graph.instagram.com/me"
    params = {
        'fields': 'id,username',
        'access_token': access_token
    }
    
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print("Error fetching user info:", response.json())
        return None

# === Background worker function ===
def background_worker():
    while True:
        print("Background worker checking for new mentions...")
        try:
            new_mentions = fetch_mentions()
            print(f"Downloaded {new_mentions} new mentions")
        except Exception as e:
            print(f"Error in background worker: {e}")
        
        time.sleep(CHECK_INTERVAL)

# === OAuth Routes ===
@app.route('/auth')
def auth():
    config = load_config()
    # Use the Instagram app ID for Instagram Basic Display API
    app_id = config.get('app_id', '1364365191512060')  # Default to provided Instagram app ID
    app_secret = config.get('app_secret', '74f06f062dbb5285c10df40f0ec0393f')  # Default to provided Instagram app secret
    redirect_uri = config.get('redirect_uri', request.url_root + 'auth/callback')
    
    auth_url = ''
    if app_id and app_secret:
        # Use Instagram Basic Display API
        auth_url = f"https://api.instagram.com/oauth/authorize?client_id={app_id}&redirect_uri={urllib.parse.quote(redirect_uri)}&scope=user_profile,user_media&response_type=code"
    
    return render_template('auth.html', 
                          app_id=app_id,
                          app_secret=app_secret,
                          redirect_uri=redirect_uri,
                          auth_url=auth_url)

@app.route('/save_app_info', methods=['POST'])
def save_app_info():
    app_id = request.form.get('app_id', '')
    app_secret = request.form.get('app_secret', '')
    redirect_uri = request.form.get('redirect_uri', request.url_root + 'auth/callback')
    
    config = load_config()
    config['app_id'] = app_id
    config['app_secret'] = app_secret
    config['redirect_uri'] = redirect_uri
    save_config(config)
    
    flash('App information saved successfully!', 'success')
    return redirect(url_for('auth'))

@app.route('/auth/callback')
def auth_callback():
    code = request.args.get('code')
    error = request.args.get('error')
    error_reason = request.args.get('error_reason')
    error_description = request.args.get('error_description')
    
    if error:
        flash(f'Authorization failed: {error_reason} - {error_description}', 'danger')
        return redirect(url_for('auth'))
        
    if not code:
        flash('Authorization failed: No code provided', 'danger')
        return redirect(url_for('auth'))
    
    config = load_config()
    app_id = config.get('app_id', '1364365191512060')
    app_secret = config.get('app_secret', '74f06f062dbb5285c10df40f0ec0393f')
    redirect_uri = config.get('redirect_uri')
    
    try:
        # Exchange code for Instagram access token
        token_url = 'https://api.instagram.com/oauth/access_token'
        data = {
            'client_id': app_id,
            'client_secret': app_secret,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
            'code': code
        }
        
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        short_lived_token = token_data.get('access_token')
        user_id = token_data.get('user_id')
        
        if not short_lived_token or not user_id:
            flash('Failed to get access token or user ID', 'danger')
            return redirect(url_for('auth'))
        
        # Exchange short-lived token for long-lived token
        long_lived_url = 'https://graph.instagram.com/access_token'
        params = {
            'grant_type': 'ig_exchange_token',
            'client_secret': app_secret,
            'access_token': short_lived_token
        }
        
        response = requests.get(long_lived_url, params=params)
        response.raise_for_status()
        
        token_data = response.json()
        long_lived_token = token_data.get('access_token')
        
        if not long_lived_token:
            flash('Failed to get long-lived token', 'danger')
            return redirect(url_for('auth'))
        
        # Get user info using the long-lived token
        user_info_url = 'https://graph.instagram.com/me'
        params = {
            'fields': 'id,username',
            'access_token': long_lived_token
        }
        
        response = requests.get(user_info_url, params=params)
        response.raise_for_status()
        
        user_info = response.json()
        username = user_info.get('username')
        
        # Save the token and user ID to config
        config['access_token'] = long_lived_token
        config['ig_user_id'] = user_id
        save_config(config)
        
        # Update global variables
        global ACCESS_TOKEN, IG_USER_ID
        ACCESS_TOKEN = long_lived_token
        IG_USER_ID = user_id
        
        flash(f'Successfully connected to Instagram as @{username}!', 'success')
            
    except requests.exceptions.HTTPError as e:
        error_details = ""
        try:
            error_json = e.response.json()
            error_details = f": {error_json.get('error', {}).get('message', str(e))}"
        except:
            error_details = f": {str(e)}"
        
        flash(f'Error during authorization{error_details}', 'danger')
        print(f"Authorization error: {error_details}")
        
    except Exception as e:
        flash(f'Unexpected error during authorization: {str(e)}', 'danger')
        print(f"Unexpected authorization error: {str(e)}")
        
    return redirect(url_for('index'))

# === Main Routes ===
@app.route('/')
def index():
    mentions = get_mentions()
    has_credentials = bool(ACCESS_TOKEN and IG_USER_ID)
    return render_template('index.html', mentions=mentions, has_credentials=has_credentials)

@app.route('/check-now')
def check_now():
    if not ACCESS_TOKEN or not IG_USER_ID:
        flash("Instagram credentials not configured. Please connect your account first.", "warning")
        return redirect(url_for('auth'))
        
    try:
        new_mentions = fetch_mentions()
        if new_mentions:
            flash(f"Downloaded {new_mentions} new mentions!", "success")
        else:
            flash("No new mentions found.", "info")
    except Exception as e:
        flash(f"Error checking mentions: {str(e)}", "danger")
    
    return redirect(url_for('index'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    global CHECK_INTERVAL
    config = load_config()
    
    if request.method == 'POST':
        try:
            check_interval = int(request.form.get('check_interval', CHECK_INTERVAL))
            if check_interval < 300:  # Minimum 5 minutes
                check_interval = 300
                
            config['check_interval'] = check_interval
            save_config(config)
            
            CHECK_INTERVAL = check_interval
            
            flash("Settings updated successfully!", "success")
        except ValueError:
            flash("Invalid check interval value", "danger")
            
        return redirect(url_for('settings'))
        
    return render_template('settings.html', 
                          access_token=config.get('access_token', ''),
                          ig_user_id=config.get('ig_user_id', ''),
                          check_interval=config.get('check_interval', CHECK_INTERVAL))

@app.route('/disconnect')
def disconnect():
    config = load_config()
    config['access_token'] = ''
    config['ig_user_id'] = ''
    save_config(config)
    
    global ACCESS_TOKEN, IG_USER_ID
    ACCESS_TOKEN = ''
    IG_USER_ID = ''
    
    flash("Instagram account disconnected successfully", "success")
    return redirect(url_for('auth'))

if __name__ == "__main__":
    init_csv()
    
    # Start background worker in a separate thread
    worker_thread = threading.Thread(target=background_worker, daemon=True)
    worker_thread.start()
    
    # Start Flask app
    app.run(debug=True, host='0.0.0.0', port=4000) 