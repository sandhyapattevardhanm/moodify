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

# Required scopes for playlist creation
SCOPE = "playlist-read-private playlist-modify-public playlist-modify-private"

# Load master dataset (precomputed features)
MASTER_DF = pd.read_csv("data/SingerAndSongs.csv")


# --- Credential Loader ---
def _get_credentials():
    """Get Spotify credentials based on environment."""
    client_id = None
    client_secret = None
    redirect_uri = None

    # If running on Streamlit Cloud → always use secrets
    if st.runtime.exists():  # We're in Streamlit runtime
        client_id = st.secrets.get("SPOTIPY_CLIENT_ID")
        client_secret = st.secrets.get("SPOTIPY_CLIENT_SECRET")
        redirect_uri = st.secrets.get("SPOTIPY_REDIRECT_URI")
    else:
        # Local dev → use .env
        from dotenv import load_dotenv
        load_dotenv()
        client_id = os.getenv("SPOTIPY_CLIENT_ID")
        client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
        redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI")

    if not all([client_id, client_secret, redirect_uri]):
        st.error("Missing Spotify credentials. Check your secrets or .env file.")
        st.stop()

    return client_id, client_secret, redirect_uri


# --- Cache Path ---
def _get_cache_path():
    """Unique cache path per session."""
    if "sp_cache" not in st.session_state:
        st.session_state["sp_cache"] = f".cache-{uuid.uuid4().hex}"
    return st.session_state["sp_cache"]


# --- Playlist ID Extractor ---
def _extract_playlist_id(url: str) -> str:
    match = re.search(r"playlist/([a-zA-Z0-9]+)", url)
    if match:
        return match.group(1)
    raise ValueError("Invalid Spotify playlist URL")


# --- Public Client (No Login) ---
def get_public_client():
    """Spotipy client without user login, for reading public playlists."""
    client_id, client_secret, _ = _get_credentials()
    return spotipy.Spotify(auth_manager=spotipy.oauth2.SpotifyClientCredentials(
        client_id=client_id,
        client_secret=client_secret
    ))


# --- Authenticated Client (Login Required) ---
def get_authenticated_client():
    """Spotipy client with user login (needed for creating playlists)."""
    client_id, client_secret, redirect_uri = _get_credentials()
    cache_path = _get_cache_path()

    sp_oauth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=SCOPE,
        cache_path=cache_path,
        show_dialog=True
    )

    # Handle Spotify redirect with ?code=...
    query_params = st.query_params
    if "code" in query_params:
        code = query_params["code"][0] if isinstance(query_params["code"], list) else query_params["code"]
        token_info = sp_oauth.get_access_token(code, as_dict=True)
        st.query_params.clear()
        st.session_state["sp_token_info"] = token_info

    # Get stored or cached token
    token_info = st.session_state.get("sp_token_info") or sp_oauth.get_cached_token()
    if not token_info:
        auth_url = sp_oauth.get_authorize_url()
        st.markdown(f"[🔐 Login to Spotify to Create Playlist]({auth_url})")
        st.stop()

    return spotipy.Spotify(auth=token_info["access_token"])


# --- Playlist Analysis ---
def get_playlist_tracks_matched(playlist_url):
    """Return DataFrame of matched songs from a public playlist."""
    sp = get_public_client()

    try:
        playlist_id = _extract_playlist_id(playlist_url)
        results = sp.playlist_tracks(playlist_id)
    except spotipy.exceptions.SpotifyException:
        st.error("Unable to access this playlist. Make sure it's public.")
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

        for _, row in MASTER_DF.iterrows():
            row_song = str(row.get("Song name", "")).strip().lower()
            row_singer = str(row.get("Singer", "")).strip().lower()
            if song_name and singer_name and \
               (song_name in row_song or row_song in song_name) and \
               (singer_name in row_singer or row_singer in singer_name):
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


# --- Playlist Creation ---
def create_mood_playlist(original_url, mood, track_uris):
    """Create playlist in logged-in user's account."""
    sp = get_authenticated_client()

    try:
        user = sp.current_user()
    except Exception:
        st.error("Failed to fetch current user. Please log in again.")
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
