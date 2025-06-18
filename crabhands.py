import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import CacheFileHandler

import json
import os
import sys
from datetime import datetime, timedelta
import logging
import argparse

def log_and_print_info(message):
    logger.info(message)
    print(f"[INFO]: {message}")

def log_and_print_warning(message):
    logger.warning(message)
    print(f"[WARNING]: {message}")

def log_and_print_error(message):
    logger.error(message)
    print(f"[ERROR]: {message}")

def log_and_print_critical(message):
    logger.critical(message)
    print(f"[CRITICAL]: {message}")

def load_user_cache(cache_file):
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_user_cache(cache_data, cache_file):
    with open(cache_file, "w") as f:
        json.dump(cache_data, f, indent=4)

def get_saved_tracks(sp):
    """
    Fetches all saved tracks from the user's Spotify library.
    Prints the index, artist name, and track name for each saved track.
    """
    results = sp.current_user_saved_tracks()
    limit = 50
    offset = 0
    tracks = []

    while True:
        results = sp.current_user_saved_tracks(limit=limit, offset=offset)
        if not results["items"]:
            break
        
        tracks.extend(results["items"])
        offset += limit

    for idx, item in enumerate(tracks):
        track = item["track"]
        print(idx, track["artists"][0]["name"], " – ", track["name"])

def get_followed_artists(sp) -> list:
    """
    Fetches all followed artists from the user"s Spotify account.
    It's not really worth it to try to do anything smart here, just fetch all artists. 
    We wouldn't be able to track unfollowed artists or rearrangments of the lists of artists without doing a full fetch every time.
    """
    limit = 50
    after = None
    followed_artists = []
    while True:
        results = sp.current_user_followed_artists(limit=limit, after=after)
        if not results["artists"]["items"]:
            break
        
        for artist in results["artists"]["items"]:
            followed_artists.append((artist["id"], artist["name"]))
            # print(f"Added artist: {followed_artists[-1]}" )
        
        after = results["artists"]["cursors"]["after"]
        if not after:
            break
    return followed_artists

def create_or_get_crabhands_playlist(sp, playlist_id: str = None) -> str:
    """
    Creates a new playlist for the user if it doesn"t already exist.
    Returns the playlist ID.
    """
    name = "crabhands"
    description = "A playlist of new releases from followed artists. Created by crabhands.py script."

    #check if a playlist already exists with same ID
    if playlist_id:
        try:
            playlist = sp.playlist(playlist_id)
            return playlist_id
        except spotipy.exceptions.SpotifyException as e:
            log_and_print_warning(f"Couldn't fetch cached playlist ID {playlist_id}: {e}, will create a new one...")

    # make playlist otherwise
    user_id = sp.current_user()["id"]
    playlist = sp.user_playlist_create(user_id, name, public=False, description=description)
    log_and_print_info(f"Created playlist: {playlist['name']} ({playlist['id']})")
    return playlist["id"]

def populate_playlist(sp, playlist_id: str, artist_ids: list, days_lookback: int = 7):
    """
    Populates the playlist with new releases from the followed artists within the last n days.
    Only adds tracks that are not already on the playlist.
    """
    limit = 50
    release_date_limit = (datetime.now() - timedelta(days=days_lookback)).strftime('%Y-%m-%d')

    # Get all existing track URIs in the playlist
    existing_uris = set()
    offset = 0
    while True:
        playlist_tracks = sp.playlist_items(playlist_id, fields="items.track.uri,next", limit=100, offset=offset)
        items = playlist_tracks.get("items", [])
        for item in items:
            track = item.get("track")
            if track and track.get("uri"):
                existing_uris.add(track["uri"])
        if not playlist_tracks.get("next"):
            break
        offset += 100

    for artist in artist_ids:
        artist_id, artist_name = artist
        albums = sp.artist_albums(artist_id, limit=limit, album_type="album,single")

        for album in albums['items']:
            # Parse album release date to datetime object for robust comparison
            release_date = album['release_date']
            precision = album.get('release_date_precision', 'day')
            if precision == 'day':
                album_date = datetime.strptime(release_date, '%Y-%m-%d')
            elif precision == 'month':
                album_date = datetime.strptime(release_date, '%Y-%m')
            elif precision == 'year':
                album_date = datetime.strptime(release_date, '%Y')
            else:
                # If unknown precision, skip this album
                continue
                
            release_date_limit_dt = datetime.strptime(release_date_limit, '%Y-%m-%d')

            # Check if album release date is within the last n days
            if album_date >= release_date_limit_dt:
                album_tracks = sp.album_tracks(album['id'])
                track_uris = [track['uri'] for track in album_tracks['items'] if track['uri'] not in existing_uris]

                if track_uris:
                    sp.playlist_add_items(playlist_id, track_uris)
                    log_and_print_info(f"Added {len(track_uris)} tracks from {artist_name}'s album '{album['name']}'")
                    existing_uris.update(track_uris)

def remove_old_tracks_from_playlist(sp, playlist_id: str, old_track_threshold: int):
    """
    Removes tracks from the playlist that were added more than old_track_threshold days ago.
    """
    tracks_to_remove = [
        track["track"]["uri"]
        for track in sp.playlist(playlist_id)["tracks"]["items"]
        if track.get("track") is not None
        and track["track"].get("uri") is not None
        and "added_at" in track
        and (datetime.now() - datetime.strptime(track["added_at"], '%Y-%m-%dT%H:%M:%SZ')).days > old_track_threshold
    ]
    if tracks_to_remove:
        sp.playlist_remove_all_occurrences_of_items(playlist_id, tracks_to_remove) #TODO handle if we have more than 100 tracks to remove
        log_and_print_info(f"Removed {len(tracks_to_remove)} old tracks from the playlist")
    else:
        log_and_print_info("No old tracks to remove from the playlist")


if __name__ == "__main__":
    logging.basicConfig(filename="crabhands.log",
                        format='%(asctime)s - %(levelname)s - %(message)s',   
                        level=logging.INFO,
                        datefmt='%Y-%m-%d %H:%M:%S')
    
    logger = logging.getLogger(__name__)

    log_and_print_info(f"Starting script at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", )

    parser = argparse.ArgumentParser(description="Crabhands Spotify Script")
    parser.add_argument("--track-freshness", type=int, default=7, help="Maximum number of days to look back for new releases (default: 7)")
    parser.add_argument("--old-track-threshold", type=int, default=30, help="Number of days after which tracks are considered old and removed from the playlist (default: 30)")
    parser.add_argument("--user-ids", type=str, default="", help="Comma-separated list of Spotify user IDs to process (default: none). If not provided, the script will use the user account associated with the provided credentials.")
    args = parser.parse_args()

    logger.info(f"Script called with --track-freshness: {args.track_freshness} days, --old-track-threshold: {args.old_track_threshold} days")
    
    scopes = "user-library-read," \
            "user-follow-read," \
            "playlist-modify-private," \
            "playlist-read-private," \

    # Get client credentials from environment variables
    client_id = os.environ.get('SPOTIFY_CLIENT_ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
    redirect_uri = os.environ.get('SPOTIFY_REDIRECT_URI', 'http://127.0.0.1:1815')

    if not client_id or not client_secret:
        log_and_print_critical("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables must be set with your Spotify app credentials.")
        sys.exit()
    
    if not redirect_uri:
        log_and_print_warning("SPOTIFY_REDIRECT_URI environment variable not set, using default: http://127.0.0.1:1815 for redirect URI. Ensure this matches your Spotify app settings.")
    
    def get_spotify_client_for_user(user_unique_id):
        """
        Authorizes the user and returns a Spotipy client object.
        Caches the token using a CacheFileHandler.
        """
        # Create a unique cache file path for each user
        cache_file_path = f".cache-{user_unique_id}"
        cache_handler = CacheFileHandler(cache_path=cache_file_path)
        
        sp_oauth = SpotifyOAuth(
                            client_id=client_id,
                            client_secret=client_secret,
                            redirect_uri=redirect_uri,
                            scope=scopes,
                            cache_handler=cache_handler, 
                            show_dialog=True)

        token_info = sp_oauth.get_cached_token()

        if not token_info:
            auth_url = sp_oauth.get_authorize_url()
            print(f"Please log in for user {user_unique_id} at: {auth_url}")
            print("If you are authenticating multiple users, please ensure you are logged in to the correct Spotify account in your browser. Use a private/incognito window if necessary.")

            response = input("Paste the Spotify redirect URL here: ")
            code = sp_oauth.parse_response_code(response)
            token_info = sp_oauth.get_access_token(code)

        if token_info:
            return spotipy.Spotify(auth_manager=sp_oauth)
        else:
            log_and_print_error(f"Couldn't get token for {user_unique_id}")
            return None
    
    # Create list of Spotify clients to go through from the user-ids given
    sps = []
    if args.user_ids:
        user_ids = [user_id.strip() for user_id in args.user_ids.split(",") if user_id.strip()]
        for user_id in user_ids:
            try:
                client = get_spotify_client_for_user(user_id)
                if not client:
                    log_and_print_error(f"Failed to create Spotify client for user {user_id}, skipping...")
                    continue
                # Check if the client is valid
                if client.current_user():
                    log_and_print_info(f"Successfully authenticated Spotify client for User ID: {user_id}")
                    sps.append(client)
                else:
                    log_and_print_warning(f"Spotify client for User ID: {user_id} is not valid, skipping...")
                    continue
            except Exception as e:
                log_and_print_critical(f"Exiting script due to error with user authentication: {e}. User ID {user_id}")
                sys.exit()
    else:
        log_and_print_info("No User ID provided, using default Spotify client")    
        sps = [spotipy.Spotify(auth_manager=SpotifyOAuth(
                                            client_id=client_id,
                                            client_secret=client_secret,
                                            redirect_uri=redirect_uri,
                                            scope=scopes,
                                            open_browser=True))]
    for sp in sps:        
        user = sp.current_user()
        log_and_print_info(f"Logged in as {user['display_name']} ({user['id']})")

        cache_file = f"user-{user['id']}.json"
        
        # Load user cache if exists
        user_cache = load_user_cache(cache_file)

        if not user_cache:
            user_cache = { "user": {
                                    "user_id": user["id"],
                                    "display_name": user["display_name"],
                                    "followed_artists": [],
                                    # "followed_playlists": [],          
                                    },
                            "playlist_id": None,
                            # "playlist_tracks": []
                }
            
        user_cache["user"]["followed_artists"] = get_followed_artists(sp)
        
        # Get the playlist we're working on
        user_cache["playlist_id"] = create_or_get_crabhands_playlist(sp, user_cache.get("playlist_id"))
            
        # Remove old tracks from the playlist
        remove_old_tracks_from_playlist(sp, user_cache["playlist_id"], args.old_track_threshold)

        # Populate the playlist with new releases from followed artists
        populate_playlist(sp, user_cache["playlist_id"], user_cache["user"]["followed_artists"], args.track_freshness)
        
        # Save user cache
        save_user_cache(user_cache, cache_file)

        log_and_print_info(f"Script completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
