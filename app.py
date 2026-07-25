import sys
import io
import os
import traceback

# CRITICAL: Prevent PyInstaller windowed mode stdout/stderr AttributeError on module import
class DummyStream:
    def write(self, data):
        pass
    def flush(self):
        pass

if sys.stdout is None:
    sys.stdout = DummyStream()
if sys.stderr is None:
    sys.stderr = DummyStream()

def log_crash(exc):
    try:
        app_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)
        log_file = os.path.join(app_dir, "crash_log.txt")
        with open(log_file, "a") as f:
            f.write(f"\n--- CRASH AT {sys.version} ---\n")
            f.write(traceback.format_exc())
    except Exception:
        pass

try:
    import webbrowser
    import threading
    from flask import Flask, render_template, request, Response, jsonify
    from config import Config
    from services.downloader import (
        fetch_video_metadata,
        start_download_jobs,
        retry_single_download,
        retry_failed_downloads,
        clear_completed_downloads,
        generate_sse_progress
    )
    from services.file_manager import (
        get_quick_dirs_service,
        list_folders_service,
        create_folder_service
    )

    # Handle PyInstaller single-file bundle extraction directory (_MEIPASS)
    if getattr(sys, 'frozen', False):
        bundle_dir = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))
        template_folder = os.path.join(bundle_dir, 'templates')
        static_folder = os.path.join(bundle_dir, 'static')
        app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
    else:
        app = Flask(__name__)

    app.config.from_object(Config)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/api/video_info', methods=['POST'])
    def get_video_info():
        data = request.get_json() or {}
        url = data.get('url', '').strip()
        if not url:
            return jsonify({'success': False, 'message': 'No URL provided'}), 400

        info = fetch_video_metadata(url)
        return jsonify({'success': True, 'data': info})

    @app.route('/api/quick_dirs', methods=['GET'])
    def quick_dirs():
        res = get_quick_dirs_service()
        return jsonify({
            'success': True,
            'system': res['system'],
            'directories': res['directories']
        })

    @app.route('/api/list_folders', methods=['POST'])
    def list_folders():
        data = request.get_json() or {}
        start_path = data.get('path', '')
        res = list_folders_service(start_path)
        if not res.get('success'):
            return jsonify(res), 400
        return jsonify(res)

    @app.route('/api/create_folder', methods=['POST'])
    def create_folder():
        data = request.get_json() or {}
        parent_path = data.get('parent_path', '')
        folder_name = data.get('folder_name', '')
        res = create_folder_service(parent_path, folder_name)
        if not res.get('success'):
            return jsonify(res), 400
        return jsonify(res)

    @app.route('/api/download', methods=['POST'])
    def start_downloads():
        data = request.get_json() or {}
        download_path = data.get('download_path', '').strip()
        videos = data.get('videos', [])

        if not download_path:
            return jsonify({'success': False, 'message': 'Please provide a valid download path.'}), 400

        if not videos:
            return jsonify({'success': False, 'message': 'No video URLs provided.'}), 400

        global_quality = data.get('quality', 'best').strip()
        started_downloads = start_download_jobs(download_path, videos, global_quality)

        return jsonify({
            'success': True,
            'message': f'Started {len(started_downloads)} downloads.',
            'downloads': started_downloads
        })

    @app.route('/api/retry_download', methods=['POST'])
    def retry_download():
        data = request.get_json() or {}
        download_id = data.get('id', '')
        quality = data.get('quality', 'best')
        success, message = retry_single_download(download_id, quality)
        return jsonify({'success': success, 'message': message})

    @app.route('/api/retry_failed', methods=['POST'])
    def retry_all_failed():
        data = request.get_json() or {}
        quality = data.get('quality', 'best')
        retried_count = retry_failed_downloads(quality)
        return jsonify({'success': True, 'count': retried_count})

    @app.route('/api/clear', methods=['POST'])
    def clear_completed():
        clear_completed_downloads()
        return jsonify({'success': True})

    @app.route('/progress')
    def progress():
        return Response(generate_sse_progress(), mimetype='text/event-stream')
 
    @app.route('/api/download_file/<download_id>')
    def download_file_route(download_id):
        from services.downloader import download_progress, download_lock
        from flask import send_file
        import os
 
        with download_lock:
            item = download_progress.get(download_id)
 
        if not item or item.get('status') != 'completed':
            return jsonify({'success': False, 'message': 'File not found or download not completed.'}), 404
 
        file_path = item.get('file_path')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'success': False, 'message': 'File does not exist on server disk.'}), 404
 
        return send_file(file_path, as_attachment=True)

    def open_browser():
        try:
            webbrowser.open_new(f"http://127.0.0.1:{Config.PORT}")
        except Exception:
            pass

    if __name__ == '__main__':
        print("\n" + "=" * 65)
        print("   ROY'S YOUTUBE DOWNLOADER PRO IS NOW RUNNING!")
        print(f"   Opening Browser at: http://127.0.0.1:{Config.PORT}")
        print("   (Keep this black window open while using the app)")
        print("=" * 65 + "\n")

        if not os.environ.get("WERKZEUG_RUN_MAIN"):
            threading.Timer(1.0, open_browser).start()
        app.run(debug=False, host='127.0.0.1', port=Config.PORT, threaded=Config.THREADED)

except Exception as ex:
    log_crash(ex)
    raise ex
