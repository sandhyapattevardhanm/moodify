import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import os

# Load credentials from env or hardcode them (not recommended for deployment)
client_id = "4dcaf9bdb5c84c5397a12a653bb828b5"
client_secret = "9fd8f33acd7245a697a045138be2017f"
redirect_uri = "http://127.0.0.1:8501"

scope = "playlist-modify-public playlist-modify-private"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope
))

# === Load master dataset ===
master_df = pd.read_csv("data/SingerAndSongs.csv")

def get_playlist_tracks_matched(playlist_url):
    playlist_id = playlist_url.split("/")[-1].split("?")[0]
    results = sp.playlist_tracks(playlist_id)

    matched_rows = []

    for item in results["items"]:
        track = item.get("track", {})
        song_name = track.get("name", "").strip().lower()
        artists = track.get("artists", [])
        singer_name = artists[0]["name"].strip().lower() if artists else ""
        uri = track.get("uri", "")

        # Try to match with master dataset
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
                break  # Stop after first match

    return pd.DataFrame(matched_rows)

def create_mood_playlist(original_url, mood, track_uris):
    user = sp.current_user()
    print(f"✅ Logged in as: {user['display_name']}")
    user_id = user["id"]

    playlist_id = original_url.split("/")[-1].split("?")[0]
    original = sp.playlist(playlist_id)
    original_name = original["name"]

    new_playlist_name = f"{original_name} - {mood}"
    new_playlist = sp.user_playlist_create(user=user_id, name=new_playlist_name, public=True)
    print(f"📀 Created playlist: {new_playlist_name}")

    if track_uris:
        sp.playlist_add_items(new_playlist["id"], track_uris[:100])
        print(f"✅ Added {len(track_uris[:100])} tracks to playlist.")
    else:
        print("⚠️ No tracks to add.")

    return new_playlist.get("external_urls", {}).get("spotify", None)
