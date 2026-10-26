import glob
import os
import shutil
import uuid

from flask import Flask, after_this_request, jsonify, render_template, request, send_file
import yt_dlp

app = Flask(__name__)

# CORS: lets a page hosted elsewhere (e.g. a Blogger page) call this API.
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        resp = app.response_class("", status=200)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        return resp


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

QUALITIES = {
    "best": "bestvideo+bestaudio/best",
    "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
    "720": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "480": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
    "360": "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
    "audio": "bestaudio/best",
}


def _ffmpeg_location():
    """Return a directory holding ffmpeg AND ffprobe, or None.

    None means "use whatever is on PATH". Order of preference:
    1. System ffmpeg+ffprobe on PATH (best, no extra downloads).
    2. The pip-bundled imageio-ffmpeg copy, if it has both binaries
       (it usually ships ffmpeg only, so this often falls through).
    3. A static ffmpeg/ffprobe build fetched on first use
       (static-ffmpeg) — this is what makes MP3 work on hosting
       without system ffmpeg, e.g. Render's free plan.
    """
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return None
    try:
        import imageio_ffmpeg
        d = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
        files = os.listdir(d)
        if (any(f.startswith("ffmpeg") for f in files)
                and any(f.startswith("ffprobe") for f in files)):
            return d
    except Exception:
        pass
    try:
        from static_ffmpeg import run
        ffmpeg_path, _ffprobe_path = run.get_or_fetch_platform_executables_else_raise()
        return os.path.dirname(ffmpeg_path)
    except Exception:
        pass
    return None


def base_opts():
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        # A real browser user-agent: some hosts reject yt-dlp's default one.
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/126.0 Safari/537.36",
        },
        # Bot-check bypass: YouTube's web client often answers a server IP
        # with "Sign in to confirm you're not a bot", while the app-based
        # clients usually do not. yt-dlp tries these in order and falls
        # back to web if the others cannot serve a video, so no cookies are
        # needed for most videos.
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "tv", "web"],
            },
        },
    }
        # If a browser-exported cookies.txt is available, yt-dlp uses it.
    # This is the standard fix when YouTube answers "Sign in to confirm)
    # you're not a bot" from a server IP. Checked locations: next to
    # app.py (local runs) and Render's secret-file directory.
    cookiefile = None
    for candidate in (
        os.path.join(BASE_DIR, "cookies.txt"),
        "/etc/secrets/cookies.txt",
        os.environ.get("COOKIES_FILE", ""),
    ):
        if candidate and os.path.exists(candidate):
            cookiefile = candidate
            break
    if cookiefile:
        opts["cookiefile"] = cookiefile
    if ffmpeg_location:
        opts["ffmpeg_location"] = ffmpeg_location
    return opts


def valid_url(url):
    return isinstance(url, str) and url.startswith(("http://", "https://"))


def cleanup_job(job):
    for f in glob.glob(os.path.join(DOWNLOAD_DIR, job + ".*")):
        try:
            os.remove(f)
        except OSError:
            pass


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/info", methods=["POST"])
def info():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not valid_url(url):
        return jsonify({"error": "Please paste a valid video link."}), 400
    opts = base_opts()
    opts["skip_download"] = True
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            meta = ydl.extract_info(url, download=False)
    except Exception as exc:
        return jsonify({"error": f"Could not read this video: {exc}"}), 400
    return jsonify({
        "title": meta.get("title") or "Untitled video",
        "uploader": meta.get("uploader") or "",
        "thumbnail": meta.get("thumbnail") or "",
        "duration": meta.get("duration") or 0,
    })


@app.route("/api/download", methods=["POST"])
def download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    quality = data.get("quality") or "best"
    if not valid_url(url):
        return jsonify({"error": "Please paste a valid video link."}), 400
    if quality not in QUALITIES:
        return jsonify({"error": "Unknown quality selected."}), 400

    job = uuid.uuid4().hex
    outtmpl = os.path.join(DOWNLOAD_DIR, job + ".%(ext)s")
    opts = base_opts()
    opts["outtmpl"] = outtmpl
    opts["format"] = QUALITIES[quality]
    if quality == "audio":
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            meta = ydl.extract_info(url, download=True)
    except Exception as exc:
        cleanup_job(job)
        return jsonify({"error": f"Download failed: {exc}"}), 400

    matches = sorted(glob.glob(os.path.join(DOWNLOAD_DIR, job + ".*")))
    if not matches:
        return jsonify({"error": "Download finished but the file was not found."}), 500
    path = matches[0]
    title = (meta.get("title") or "video").strip()
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip() or "video"
    ext = os.path.splitext(path)[1].lstrip(".") or "mp4"
    download_name = f"{safe_title}.{ext}"

    @after_this_request
    def cleanup(response):
        try:
            os.remove(path)
        except OSError:
            pass
        return response

    return send_file(path, as_attachment=True, download_name=download_name)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
