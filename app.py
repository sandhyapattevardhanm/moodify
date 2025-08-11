import os
for f in os.listdir():
    if f.startswith(".cache"):
        os.remove(f)
import streamlit as st
import pandas as pd
import pickle
from spotify_utils import get_playlist_tracks_matched, create_mood_playlist

model = pickle.load(open("KNN_Model.pkl", "rb"))

st.set_page_config(page_title="Spotify Mood Classifier", layout="centered")
st.title("🎵 Spotify Playlist Mood Classifier")
st.write("Filter your Spotify playlist by mood and create a new one instantly!")

if "filtered" not in st.session_state:
    st.session_state.filtered = None
if "track_uris" not in st.session_state:
    st.session_state.track_uris = None
if "playlist_url" not in st.session_state:
    st.session_state.playlist_url = ""
if "mood_text" not in st.session_state:
    st.session_state.mood_text = ""

playlist_url = st.text_input("Enter your public Spotify playlist URL:")
mood_option = st.radio("Select mood to filter:", ["Happy 😊", "Sad 😭"])

if st.button("Analyze Playlist") and playlist_url:
    with st.spinner("🎧 Fetching songs..."):
        df = get_playlist_tracks_matched(playlist_url)

    if df.empty:
        st.warning("😕 No songs matched with the dataset.")
    else:
        preds = model.predict(df[["energy", "valence", "tempo"]])
        df["Mood"] = ["Happy 😊" if p == 0 else "Sad 😭" for p in preds]

        filtered = df[df["Mood"] == mood_option]
        st.session_state.filtered = filtered
        st.session_state.track_uris = filtered["uri"].tolist()
        st.session_state.playlist_url = playlist_url
        st.session_state.mood_text = "Happy" if mood_option == "Happy 😊" else "Sad"

        st.success(f"🎯 Found {len(filtered)} '{mood_option}' songs out of {len(df)} total.")
        st.dataframe(filtered[["Singer", "Song name", "Mood"]])

if st.session_state.filtered is not None:
    if st.button("🎵 Yes, create playlist"):
        with st.spinner("🛠 Creating playlist..."):
            new_url = create_mood_playlist(
                st.session_state.playlist_url,
                st.session_state.mood_text,
                st.session_state.track_uris,
            )
            st.success("✅ Playlist created successfully!")
            st.markdown(f"[🎧 Open Your New Playlist]({new_url})", unsafe_allow_html=True)
