# spotify_utils.py
import os
import re
import uuid
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Load local .env (only if present)
load_dotenv()

# Required scopes
SCOPE = "playlist-read-private playlist-modify-public playlist-modify-private"

# Helper to read credentials (cloud via st.secrets else .env/local)
def _get_credentials():
    client_id = None
    client_secret = None
    redirect_uri = None

    # First try Streamlit secrets (deployed)
    if st.secrets and "SPOTIPY_CLIENT_ID" in st.secrets:
        client_id = st.secrets["SPOTIPY_CLIENT_ID"]
        client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
        redirect_uri = st.secrets.get("SPOTIPY_REDIRECT_URI")
    # Fallback to environment (.env) for local dev
    client_id = client_id or os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = client_secret or os.getenv("SPOTIPY_CLIENT_SECRET")
    redirect_uri = redirect_uri or os.getenv("SPOTIPY_REDIRECT_URI") or "http://127.0.0.1:8501"

    return client_id, client_secret, redirect_uri

# Create a unique cache file name for this session (prevents token mix-up)
def _get_cache_path():
    if "sp_cache" not in st.session_state:
        st.session_state["sp_cache"] = f".cache-{uuid.uuid4().hex}"
    return st.session_state["sp_cache"]

def _extract_playlist_id(url: str) -> str:
    match = re.search(r"playlist/([a-zA-Z0-9]+)", url)
    if match:
        return match.group(1)
    raise ValueError("Invalid Spotify playlist URL")

def get_spotify_client():
    """
    Returns an *authenticated* spotipy.Spotify instance for the current user.
    If user hasn't logged in, shows a login link and stops the app.
    """

    client_id, client_secret, redirect_uri = _get_credentials()
    if not (client_id and client_secret and redirect_uri):
        st.error("Missing Spotify app credentials. Locally put them in a .env file; on Streamlit Cloud add them to Secrets.")
        st.stop()

    cache_path = _get_cache_path()

    sp_oauth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=SCOPE,
        cache_path=cache_path,
        show_dialog=True
    )

        # If Spotify redirected back with ?code=... Streamlit will have it in query params
    query_params = st.query_params
    if "code" in query_params:
        code = query_params["code"][0] if isinstance(query_params["code"], list) else query_params["code"]
        # Exchange code for token and cache it
        try:
            token_info = sp_oauth.get_access_token(code)
        except TypeError:
            token_info = sp_oauth.get_access_token(code, as_dict=True)

        # clear query params so we don't try to exchange again
        st.query_params.clear()
        st.session_state["sp_token_info"] = token_info

    # Prefer session_state stored token, else cached token
    token_info = st.session_state.get("sp_token_info") or sp_oauth.get_cached_token()

    if not token_info:
        auth_url = sp_oauth.get_authorize_url()
        st.markdown(f"[🔐 Login to Spotify]({auth_url})")
        st.stop()

    access_token = token_info["access_token"] if isinstance(token_info, dict) else token_info
    sp = spotipy.Spotify(auth=access_token)

    # Optional: show logged-in user name (non-blocking)
    try:
        user = sp.current_user()
        st.session_state["spotify_user_display_name"] = user.get("display_name")
    except Exception:
        pass

    return sp

# Load master dataset (your precomputed features)
MASTER_DF = pd.read_csv("data/SingerAndSongs.csv")

def get_playlist_tracks_matched(playlist_url):
    sp = get_spotify_client()

    try:
        playlist_id = _extract_playlist_id(playlist_url)
    except ValueError as e:
        st.error(str(e))
        st.stop()

    try:
        results = sp.playlist_tracks(playlist_id)
    except spotipy.exceptions.SpotifyException:
        st.error("Unable to access this playlist (private, region-locked, or invalid). Try a public playlist or log in with the owner account.")
        st.stop()

    matched_rows = []
    for item in results.get("items", []):
        track = item.get("track", {})
        if not track:
            continue
        song_name = track.get("name", "").strip().lower()
        artists = track.get("artists", [])
        singer_name = artists[0]["name"].strip().lower() if artists else ""
        uri = track.get("uri", "")

        # Looser matching for robustness (partial, case-insensitive)
        for _, row in MASTER_DF.iterrows():
            row_song = str(row.get("Song name", "")).strip().lower()
            row_singer = str(row.get("Singer", "")).strip().lower()
            if song_name and singer_name and (song_name in row_song or row_song in song_name) and (singer_name in row_singer or row_singer in singer_name):
                matched_rows.append({
                    "Song name": row["Song name"],
                    "Singer": row["Singer"],
                    "energy": row["energy"],
                    "valence": row["valence"],
                    "tempo": row["tempo"],
                    "uri": uri
                })
                break

    return pd.DataFrame(matched_rows)

def create_mood_playlist(original_url, mood, track_uris):
    sp = get_spotify_client()
    try:
        user = sp.current_user()
    except Exception as e:
        st.error("Failed to fetch current user. Make sure you completed login.")
        st.stop()

    st.write(f"✅ Logged in as: {user.get('display_name', user.get('id'))}")

    playlist_id = _extract_playlist_id(original_url)
    original_name = sp.playlist(playlist_id)["name"]
    new_playlist_name = f"{original_name} - {mood}"

    new_playlist = sp.user_playlist_create(user=user["id"], name=new_playlist_name, public=True)
    if track_uris:
        sp.playlist_add_items(new_playlist["id"], track_uris[:100])
        st.success(f"✅ Added {len(track_uris[:100])} songs to **{new_playlist_name}**")
    else:
        st.warning("⚠️ No tracks to add.")

    return new_playlist.get("external_urls", {}).get("spotify")
