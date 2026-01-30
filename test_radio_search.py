from yt_dlp import YoutubeDL

def test_radio_extraction(query):
    print(f"--- Testing Radio Extraction for: {query} ---")
    
    # 1. Get Video ID
    ydl_opts_search = {
        'quiet': True,
        'extract_flat': True,
        'limit': 1,
        'default_search': 'ytsearch',
    }
    
    video_id = None
    
    try:
        with YoutubeDL(ydl_opts_search) as ydl:
            print("Step 1: Finding video...")
            # FORCE prefix to ensure it searches
            search_query = f"ytsearch:{query}"
            info = ydl.extract_info(search_query, download=False)
            
            # Print keys to debug
            # print(f"DEBUG Keys: {info.keys()}")
            
            if 'entries' in info:
                # ytsearch returns a "playlist" of results
                entries = list(info['entries']) # resolve generator
                if entries:
                    first = entries[0]
                    video_id = first.get('id')
                    title = first.get('title')
                    print(f"   -> Found Video: {title} (ID: {video_id})")
                else:
                    print("   -> Search returned no entries.")
            elif 'id' in info:
                video_id = info['id']
                print(f"   -> Found Video: {info['title']} (ID: {video_id})")
            else:
                print("   -> Unknown result structure.")
    except Exception as e:
        print(f"Error in Step 1: {e}")
        return

    if not video_id:
        print("Could not find video ID.")
        return

    # 2. Extract Mix
    # Standard YouTube Mix ID format: RD + VideoID
    mix_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
    print(f"Step 2: Extracting Mix URL: {mix_url}")
    
    ydl_opts_mix = {
        'quiet': True,
        'extract_flat': 'in_playlist',
    }
    
    try:
        with YoutubeDL(ydl_opts_mix) as ydl:
            res = ydl.extract_info(mix_url, download=False)
            
            if 'entries' in res:
                entries = list(res['entries'])
                print(f"   -> Found {len(entries)} tracks in Mix.")
                if len(entries) > 0:
                    print("   -> First 3:")
                    for i in range(min(3, len(entries))):
                        print(f"      {i+1}. {entries[i].get('title')}")
            else:
                print("   -> No entries in Mix.")
                
    except Exception as e:
        print(f"Error in Step 2: {e}")

if __name__ == "__main__":
    test_radio_extraction("blinding lights")
