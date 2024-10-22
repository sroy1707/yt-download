from flask import Flask, request, render_template, Response
import yt_dlp
import os
import time

app = Flask(__name__)

# A global dictionary to store the download progress and custom titles
download_progress = {}

def progress_hook(d):
    """Hook function to update download progress."""
    if d['status'] == 'downloading':
        video_id = d['info_dict']['id']
        custom_title = download_progress.get(video_id, {}).get('custom_title', 'Unknown')
        progress = d['_percent_str']
        # Update the global dictionary with the progress
        download_progress[video_id]['progress'] = progress
        download_progress[video_id]['title'] = custom_title

def download_video(video_url, custom_name, download_path):
    try:
        # Ensure the download path exists
        if not os.path.exists(download_path):
            os.makedirs(download_path)

        ydl_opts = {
            'format': 'bestvideo[height<=720]+bestaudio/best',
            'outtmpl': os.path.join(download_path, f'{custom_name}.%(ext)s'),  # Save with custom name
            'merge_output_format': 'mp4',
            'progress_hooks': [progress_hook],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(video_url, download=False)
            video_id = result['id']
            # Store the custom title in the global dictionary
            download_progress[video_id] = {'custom_title': custom_name, 'progress': '0%'}
            ydl.download([video_url])
        return "Download successful!"
    except Exception as e:
        return f"An error occurred: {e}"

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        video_urls = [url.strip() for url in request.form['video_urls'].split(',') if url.strip()]
        custom_names = [name.strip() for name in request.form['custom_names'].split(',') if name.strip()]
        download_path = request.form['download_path'].strip()
        messages = []

        if not download_path:
            messages.append("Please provide a valid download path.")
        elif len(video_urls) != len(custom_names):
            messages.append("The number of URLs and custom names must be the same.")
        else:
            for url, custom_name in zip(video_urls, custom_names):
                result = download_video(url, custom_name, download_path)
                messages.append(f"{custom_name}: {result}")

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
                    title = data['custom_title']
                    progress = data['progress']
                    yield f"data: {title}: {progress}\n\n"
                time.sleep(1)
            else:
                yield "data: Waiting for download...\n\n"
                time.sleep(1)
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, threaded=True)