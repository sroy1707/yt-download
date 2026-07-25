#!/usr/bin/env python3
"""
ROY'S YOUTUBE DOWNLOADER CLI
A fast, robust command-line YouTube downloader built with yt-dlp.
"""

import os
import sys
import shutil

try:
    import yt_dlp
except ImportError:
    print("Error: 'yt_dlp' module is required. Install it via: pip install yt-dlp")
    sys.exit(1)


def check_ffmpeg():
    """Check if ffmpeg binary is available on the system."""
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
    if os.path.exists("/usr/bin/ffmpeg"):
        return "/usr/bin/ffmpeg"
    return None


def apply_cookies(ydl_opts):
    """Apply browser cookies if available to prevent YouTube 403 / bot errors."""
    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = "cookies.txt"
        return

    # Try local browser cookies
    browsers = ['chrome', 'firefox', 'edge', 'brave', 'opera']
    for b in browsers:
        try:
            ydl_opts['cookiesfrombrowser'] = (b,)
            break
        except Exception:
            pass


def progress_hook(d):
    """Clean terminal progress output callback."""
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '0%').strip()
        speed = d.get('_speed_str', 'N/A').strip()
        eta = d.get('_eta_str', 'N/A').strip()
        filename = os.path.basename(d.get('filename', 'video'))
        sys.stdout.write(f"\r\033[K[Downloading] {percent} | Speed: {speed} | ETA: {eta} | {filename[:30]}")
        sys.stdout.flush()
    elif d['status'] == 'finished':
        print("\n\033[32m[✓] Download & processing completed!\033[0m")


def download(url, output_dir="downloads", quality_choice="1"):
    """Core download worker."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    out_template = os.path.join(output_dir, '%(title)s.%(ext)s')

    ydl_opts = {
        'outtmpl': out_template,
        'progress_hooks': [progress_hook],
        'nocheckcertificate': True,
        'geo_bypass': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'mweb', 'web']
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }

    # FFmpeg configuration
    ffmpeg_path = check_ffmpeg()
    if ffmpeg_path:
        ydl_opts['ffmpeg_location'] = ffmpeg_path

    # Apply cookies
    apply_cookies(ydl_opts)

    # Format quality selection
    if quality_choice == '2': # 1080p
        ydl_opts['format'] = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
        ydl_opts['merge_output_format'] = 'mp4'
    elif quality_choice == '3': # 720p
        ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best[height<=720]'
        ydl_opts['merge_output_format'] = 'mp4'
    elif quality_choice == '4': # Audio Only MP3
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else: # Best Quality Default
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
        ydl_opts['merge_output_format'] = 'mp4'

    print(f"\n\033[36m▶ Starting download for: {url}\033[0m")
    print(f"📁 Save location: {os.path.abspath(output_dir)}\n")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print("\033[32mSuccess! File saved.\033[0m")
    except Exception as e:
        print(f"\n\033[31m[X] Download Error: {e}\033[0m")


def main():
    print("=" * 55)
    print("         ROY'S YOUTUBE DOWNLOADER (CLI TOOL)")
    print("=" * 55)

    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("\nEnter YouTube Video or Playlist URL: ").strip()

    if not url:
        print("No URL provided. Exiting.")
        sys.exit(0)

    print("\nSelect Quality / Format:")
    print("  [1] Best Quality Video (Default)")
    print("  [2] 1080p Full HD")
    print("  [3] 720p HD")
    print("  [4] Audio Only (MP3)")
    choice = input("Enter choice (1-4) [default: 1]: ").strip() or "1"

    dest_dir = input("\nEnter output folder [default: ./downloads]: ").strip() or "downloads"

    download(url, dest_dir, choice)


if __name__ == '__main__':
    main()
