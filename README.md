# Instagram Mention Tracker

A Flask web application that tracks and downloads media where a user is mentioned or tagged on Instagram.

## Features

- Authenticate with Instagram Basic Display API
- Automatically fetch and download media where the user is mentioned
- Display media in a web interface
- Background worker to check for new mentions at configurable intervals
- Save mention metadata to CSV

## Setup

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the application:
   ```
   python tracker.py
   ```
4. Visit http://localhost:4000 in your browser
5. Connect your Instagram account following the on-screen instructions

## Configuration

You'll need to create an Instagram app in the Meta Developer Dashboard to get the necessary app ID and secret. Configure these in the web interface. 