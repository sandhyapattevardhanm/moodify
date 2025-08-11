import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import streamlit as st

# === Spotify OAuth (user-specific) ===
scope = "playlist-modify-public playlist-modify-private"

def get_spotify_client():
    if "spotify_token" not in st.session_state:
        sp_oauth = SpotifyOAuth(
            client_id=st.secrets["SPOTIPY_CLIENT_ID"],
            client_secret=st.secrets["SPOTIPY_CLIENT_SECRET"],
            redirect_uri=st.secrets["SPOTIPY_REDIRECT_URI"],  # must match Streamlit Cloud URL
            scope=scope,
            show_dialog=True
        )

        token_info = sp_oauth.get_cached_token()
        if not token_info:
            auth_url = sp_oauth.get_authorize_url()
            st.markdown(f"[Login to Spotify]({auth_url})")
            st.stop()
        else:
            st.session_state.spotify_token = token_info["access_token"]

    return spotipy.Spotify(auth=st.session_state.spotify_token)


# === Load master dataset ===
master_df = pd.read_csv("data/SingerAndSongs.csv")


def get_playlist_tracks_matched(playlist_url):
    sp = get_spotify_client()

    playlist_id = playlist_url.split("/")[-1].split("?")[0]
    results = sp.playlist_tracks(playlist_id)
    matched_rows = []

    for item in results["items"]:
        track = item.get("track", {})
        song_name = track.get("name", "").strip().lower()
        artists = track.get("artists", [])
        singer_name = artists[0]["name"].strip().lower() if artists else ""
        uri = track.get("uri", "")

        # Match with dataset
        for _, row in master_df.iterrows():
            row_song = str(row.get("Song name", "")).strip().lower()
            row_singer = str(row.get("Singer", "")).strip().lower()

            if song_name in row_song and singer_name in row_singer:
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
    user = sp.current_user()
    st.write(f"✅ Logged in as: {user['display_name']}")

    playlist_id = original_url.split("/")[-1].split("?")[0]
    original = sp.playlist(playlist_id)
    original_name = original["name"]

    new_playlist_name = f"{original_name} - {mood}"
    new_playlist = sp.user_playlist_create(user=user["id"], name=new_playlist_name, public=True)

    if track_uris:
        sp.playlist_add_items(new_playlist["id"], track_uris[:100])
        st.success(f"✅ Added {len(track_uris[:100])} tracks to **{new_playlist_name}**")
    else:
        st.warning("⚠️ No tracks to add.")

    return new_playlist.get("external_urls", {}).get("spotify", None)
