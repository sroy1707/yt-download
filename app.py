from flask import Flask, request, render_template, Response
import yt_dlp
import os
import time

app = Flask(__name__)

# A global dictionary to store the download progress and titles
download_progress = {}

def progress_hook(d):
    """Hook function to update download progress."""
    if d['status'] == 'downloading':
        video_id = d['info_dict']['id']
        video_title = d['info_dict']['title']
        progress = d['_percent_str']
        # Update the global dictionary with the progress and title
        download_progress[video_id] = {'title': video_title, 'progress': progress}

def download_video(video_url, download_path):
    try:
        # Ensure the download path exists
        if not os.path.exists(download_path):
            os.makedirs(download_path)

        ydl_opts = {
            'format': 'bestvideo[height<=720]+bestaudio/best',
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),  # Save to specified path
            'merge_output_format': 'mp4',
            'progress_hooks': [progress_hook],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        return "Download successful!"
    except Exception as e:
        return f"An error occurred: {e}"

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        video_urls = request.form['video_urls']
        download_path = request.form['download_path'].strip()
        messages = []

        if not download_path:
            messages.append("Please provide a valid download path.")
        else:
            for url in video_urls.split(','):
                url = url.strip()
                if url:
                    result = download_video(url, download_path)
                    messages.append(f"{url}: {result}")

        return render_template('index.html', messages=messages)
    return render_template('index.html')

@app.route('/progress')
def progress():
    """Stream the download progress to the client."""
    def generate():
        while True:
            if download_progress:
                # Stream the progress as JSON string
                for video_id, data in download_progress.items():
                    title = data['title']
                    progress = data['progress']
                    yield f"data: {title}: {progress}\n\n"
                time.sleep(1)
            else:
                yield "data: Waiting for download...\n\n"
                time.sleep(1)
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, threaded=True)
