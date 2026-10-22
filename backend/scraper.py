import os
import yt_dlp
from pathlib import Path

def normalize_reels_url(page_url: str) -> str:
    url = page_url.strip().rstrip('/')
    return url + '/' if url.endswith('/reels') else url + '/reels/'

def download_facebook_reels(page_url: str, output_dir: str, max_reels: int = 30) -> list[dict]:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    reels_url = normalize_reels_url(page_url)
    
    ai_keywords = ["#ai", "#ia", "midjourney", "sora", "runway", "généré par l'ia", "ai generated"]

    def filter_reels(info, *, incomplete):
        desc = (info.get('description') or info.get('title') or '').lower()
        if any(k in desc for k in ai_keywords):
            return "Ignoré : Mots-clés IA détectés"
        return None

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]/bestvideo/best',
        'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
        'playlistend': max_reels,
        'ignoreerrors': True,
        'no_warnings': True,
        'quiet': True,
        'match_filter': filter_reels,
        # Décommente la ligne ci-dessous si Facebook bloque au bout de 4 vidéos :
        # 'cookiesfrombrowser': ('chrome',),
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
    }

    downloaded = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(reels_url, download=True)
        if not info_dict or 'entries' not in info_dict:
            return []

        for entry in info_dict['entries']:
            if not entry:
                continue
            vid_id = entry.get('id')
            vid_path = os.path.join(output_dir, f"{vid_id}.mp4")
            if os.path.exists(vid_path):
                downloaded.append({
                    "id": vid_id,
                    "path": vid_path,
                    "description": entry.get('description') or "",
                    "timestamp": entry.get('timestamp') or 0
                })
    return downloaded