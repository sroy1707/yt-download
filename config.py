import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'yt-downloader-pro-secret-key')
    PORT = int(os.environ.get('PORT', 5005))
    DEBUG = True
    THREADED = True
    COOKIES_FILE = os.path.join(os.getcwd(), 'cookies.txt')
