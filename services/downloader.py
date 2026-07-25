import os
import re
import json
import time
import uuid
import threading
import urllib.request
import urllib.parse
import yt_dlp
from config import Config

# Global download progress state protected by thread lock
download_progress = {}
download_lock = threading.Lock()

ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def clean_ansi(text):
    if not text:
        return ""
    return ansi_escape.sub('', text).strip()

def get_ffmpeg_path():
    """Returns path to pre-compiled FFmpeg binary using imageio_ffmpeg if available."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None

def normalize_youtube_url(url):
    """Normalize YouTube embed, shorts, or mobile URLs to standard watch URLs to prevent 403 Forbidden errors."""
    if not url:
        return url
    url = url.strip()
    embed_match = re.search(r'youtube\.com/embed/([a-zA-Z0-9_-]+)', url)
    if embed_match:
        return f"https://www.youtube.com/watch?v={embed_match.group(1)}"

    shorts_match = re.search(r'youtube\.com/shorts/([a-zA-Z0-9_-]+)', url)
    if shorts_match:
        return f"https://www.youtube.com/watch?v={shorts_match.group(1)}"

    return url

def apply_cookie_settings(ydl_opts):
    """Apply cookies.txt if available."""
    if os.path.exists(Config.COOKIES_FILE):
        ydl_opts['cookiefile'] = Config.COOKIES_FILE

def fetch_video_metadata(url):
    """Fetch video metadata using YouTube oEmbed endpoint with yt_dlp fallback."""
    url = normalize_youtube_url(url)

    # Fast oEmbed Title Fetching (No yt-dlp delay)
    try:
        oembed_url = f"https://www.youtube.com/oembed?url={urllib.parse.quote(url)}&format=json"
        req = urllib.request.Request(
            oembed_url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode('utf-8'))
                return {
                    'title': data.get('title', ''),
                    'thumbnail': data.get('thumbnail_url', ''),
                    'author': data.get('author_name', '')
                }
    except Exception:
        pass

    # Fallback to yt_dlp metadata extraction
    try:
        ydl_opts = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
        }

        ffmpeg_path = get_ffmpeg_path()
        if ffmpeg_path:
            ydl_opts['ffmpeg_location'] = ffmpeg_path

        apply_cookie_settings(ydl_opts)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                return {
                    'title': info.get('title', ''),
                    'thumbnail': info.get('thumbnail', ''),
                    'author': info.get('uploader', '') or info.get('channel', '')
                }
    except Exception:
        pass

    return {'title': '', 'thumbnail': '', 'author': ''}

def run_download_thread(download_id, video_url, download_path, thumbnail='', quality='best'):
    """Target function for download thread."""
    try:
        video_url = normalize_youtube_url(video_url)
        abs_download_path = os.path.abspath(download_path)
        if not os.path.exists(abs_download_path):
            os.makedirs(abs_download_path, exist_ok=True)

        outtmpl = os.path.join(abs_download_path, '%(title)s.%(ext)s')

        if quality == '1080p':
            format_str = 'bestvideo[height<=1080]+bestaudio/best'
        elif quality == '720p':
            format_str = 'bestvideo[height<=720]+bestaudio/best'
        elif quality == '480p':
            format_str = 'bestvideo[height<=480]+bestaudio/best'
        elif quality == 'audio':
            format_str = 'bestaudio/best'
        else:
            format_str = 'bestvideo+bestaudio/best'

        ydl_opts = {
            'format': format_str,
            'progress_hooks': [make_progress_hook(download_id)],
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            'geo_bypass': True,
            'nocheckcertificate': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
        }

        ffmpeg_path = get_ffmpeg_path()
        if ffmpeg_path:
            ydl_opts['ffmpeg_location'] = ffmpeg_path

        apply_cookie_settings(ydl_opts)

        if quality == 'audio':
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        with download_lock:
            if download_id in download_progress:
                download_progress[download_id]['status'] = 'downloading'
                if thumbnail:
                    download_progress[download_id]['thumbnail'] = thumbnail

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            extracted_title = info.get('title', '') if info else ''
            final_filename = info.get('_filename') if info else None
 
            with download_lock:
                if download_id in download_progress:
                    download_progress[download_id]['status'] = 'completed'
                    download_progress[download_id]['progress'] = '100%'
                    download_progress[download_id]['eta'] = '00:00'
                    download_progress[download_id]['speed'] = '0 B/s'
                    if extracted_title:
                        download_progress[download_id]['custom_title'] = extracted_title
                    if final_filename:
                        download_progress[download_id]['file_path'] = final_filename

    except Exception as e:
        error_msg = clean_ansi(str(e))
        if "Sign in to confirm" in error_msg or "bot" in error_msg:
            error_msg = "YouTube Bot/Age Verification: Please place a 'cookies.txt' file in your app directory to bypass YouTube bot challenges."

        with download_lock:
            if download_id in download_progress:
                download_progress[download_id]['status'] = 'error'
                download_progress[download_id]['error'] = error_msg

def make_progress_hook(download_id):
    """Create a progress hook function for a specific download_id."""
    def progress_hook(d):
        if d['status'] == 'downloading':
            raw_percent = d.get('_percent_str', '0%')
            percent = clean_ansi(raw_percent)
            raw_speed = d.get('_speed_str', 'N/A')
            speed = clean_ansi(raw_speed)
            raw_eta = d.get('_eta_str', 'N/A')
            eta = clean_ansi(raw_eta)

            filename = d.get('filename', '')
            base_filename = os.path.basename(filename) if filename else ''
            title_without_ext = os.path.splitext(base_filename)[0] if base_filename else ''

            info_dict = d.get('info_dict', {})
            title = info_dict.get('title') or title_without_ext

            with download_lock:
                if download_id in download_progress:
                    download_progress[download_id]['status'] = 'downloading'
                    download_progress[download_id]['progress'] = percent
                    download_progress[download_id]['speed'] = speed
                    download_progress[download_id]['eta'] = eta
                    if title and not download_progress[download_id]['custom_title']:
                        download_progress[download_id]['custom_title'] = title
        elif d['status'] == 'finished':
            with download_lock:
                if download_id in download_progress:
                    download_progress[download_id]['status'] = 'completed'
                    download_progress[download_id]['progress'] = '100%'
                    download_progress[download_id]['eta'] = '00:00'
                    download_progress[download_id]['speed'] = '0 B/s'
    return progress_hook

def start_download_jobs(download_path, videos, global_quality='best'):
    """Start background download threads for multiple video items."""
    started_downloads = []

    for item in videos:
        url = item.get('url', '').strip()
        if not url:
            continue

        download_id = str(uuid.uuid4())
        custom_title = item.get('fetched_title', '')
        thumbnail = item.get('thumbnail', '')

        with download_lock:
            download_progress[download_id] = {
                'id': download_id,
                'url': url,
                'download_path': download_path,
                'custom_title': custom_title,
                'thumbnail': thumbnail,
                'status': 'pending',
                'progress': '0%',
                'speed': '0 B/s',
                'eta': '--:--',
                'error': None
            }

        t = threading.Thread(
            target=run_download_thread,
            args=(download_id, url, download_path, thumbnail, global_quality),
            daemon=True
        )
        t.start()
        started_downloads.append(download_progress[download_id])

    return started_downloads

def retry_single_download(download_id, global_quality='best'):
    """Restart a single failed download job."""
    with download_lock:
        if download_id not in download_progress:
            return False, "Download task not found"

        item = download_progress[download_id]
        if item['status'] != 'error':
            return False, "Only failed downloads can be retried"

        item['status'] = 'pending'
        item['progress'] = '0%'
        item['speed'] = '0 B/s'
        item['eta'] = '--:--'
        item['error'] = None

        url = item['url']
        download_path = item['download_path']
        thumbnail = item.get('thumbnail', '')

    t = threading.Thread(
        target=run_download_thread,
        args=(download_id, url, download_path, thumbnail, global_quality),
        daemon=True
    )
    t.start()
    return True, "Retrying download..."

def retry_failed_downloads(global_quality='best'):
    """Restart all failed download jobs."""
    with download_lock:
        failed_ids = [
            did for did, data in download_progress.items()
            if data['status'] == 'error'
        ]

    retried_count = 0
    for did in failed_ids:
        success, _ = retry_single_download(did, global_quality)
        if success:
            retried_count += 1

    return retried_count

def clear_completed_downloads():
    """Remove completed or errored downloads from state."""
    global download_progress
    with download_lock:
        to_delete = [
            did for did, data in download_progress.items()
            if data['status'] in ('completed', 'error')
        ]
        for did in to_delete:
            del download_progress[did]

def generate_sse_progress():
    """Generator for Server-Sent Events (SSE)."""
    while True:
        with download_lock:
            data = json.dumps(list(download_progress.values()))
        yield f"data: {data}\n\n"
        time.sleep(1)
