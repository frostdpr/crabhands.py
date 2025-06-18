# crabhands.py

crabhands.py is a Python script that creates and maintains a Spotify playlist of new releases from the artists you follow. It uses [Spotipy](https://spotipy.readthedocs.io/) to interact with the Spotify Web API. Inspired by [its namesake](https://www.crabhands.com/).

## Features

- Makes a playlist called crabhands that is populated with new tracks from artists that you follow.
- Automation via crontab or Windows Task Scheduler.

## Setup

1. **Create a Spotify Developer App**  
   Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/) and create an app.  
   Note your **Client ID**, **Client Secret**, and set a Redirect URI (e.g., `http://127.0.0.1:1815`).

2. **Set Environment Variables**  
   Set the following environment variables in your shell:
   ```sh
   export SPOTIFY_CLIENT_ID='your_client_id'
   export SPOTIFY_CLIENT_SECRET='your_client_secret'
   export SPOTIFY_REDIRECT_URI='http://127.0.0.1:1815'
   ```
3. **Create and Activate a Virtual Environment**  
   It is recommended to use a Python virtual environment to manage dependencies:
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   ```
4. **Install dependencies**

   ```sh
   pip install -r requirements.txt
   ```

5. **First run**  
   You will need to allow permissions via Spotify log-in once for the script to function. A browser window should pop up. 

   For multi-account setup: It is necessary to authenticate each account in a separate browser window and give the script the redirect URL per account. 

## Automation Example
   ### On Linux/macOS (using `crontab`)

1. **Ensure your virtual environment and environment variables are set up.**  
   You may want to create a shell script (e.g., `run_crabhands.sh`) to activate your virtual environment and run the script:

   ```sh
   #!/bin/bash
   cd /path/to/crabhands
   source venv/bin/activate
   export SPOTIFY_CLIENT_ID='your_client_id'
   export SPOTIFY_CLIENT_SECRET='your_client_secret'
   export SPOTIFY_REDIRECT_URI='http://127.0.0.1:1815'
   python crabhands.py --track-freshness 
   ```

   Make the script executable:
   ```sh
   chmod +x run_crabhands.sh
   ```

2. **Edit your crontab:**
   ```sh
   crontab -e
   ```
   Add a line to run the script daily at 8:00 AM (adjust the path as needed):
   ```
   0 8 * * * /path/to/crabhands/run_crabhands.sh >> /path/to/crabhands/cron.log 2>&1
   ```
### On Windows (using Task Scheduler)

1. **Create a batch file** (e.g., `run_crabhands.bat`) with the following content:
   ```bat
   cd /d C:\path\to\crabhands
   .\venv\Scripts\Activate.ps1
   set SPOTIFY_CLIENT_ID=your_client_id
   set SPOTIFY_CLIENT_SECRET=your_client_secret
   set SPOTIFY_REDIRECT_URI=http://127.0.0.1:1815
   python crabhands.py
   ```

2. **Open Task Scheduler** and create a new task:
   - Set the trigger to your desired schedule.
   - Set the action to run your batch file.

## Optional Arguments

- `--track-freshness N`  
  Maximum number of days to look back for new releases (default: 7)

- `--old-track-threshold N`  
  Number of days after which tracks are considered old and removed from the playlist (default: 30)

- `--user-ids id1,id2,...`  
  Comma-separated list of Spotify user IDs to process (advanced/multi-user use)

