from yt_dlp import YoutubeDL
import sys

def setup_oauth():
    print("--- Starting yt-dlp OAuth2 Setup ---")
    print("This script will attempt to fetch a video using OAuth2.")
    print("If not authenticated, it should provide a URL and Code below.")
    print("Please check the output closely.")
    
    ydl_opts = {
        'username': 'oauth2',
        'password': '',
        'quiet': False, # We need to see the output!
        'no_warnings': False,
    }
    
    # Try to fetch a simple video info to trigger auth
    try:
        with YoutubeDL(ydl_opts) as ydl:
            # Using a generic video
            ydl.extract_info("https://www.youtube.com/watch?v=BaW_jenozKc", download=False)
            print("\nSUCCESS: Authentication appears to be working (or already cached)!")
    except Exception as e:
        print(f"\nExample complete (Error expected if just waiting code): {e}")

if __name__ == "__main__":
    setup_oauth()
