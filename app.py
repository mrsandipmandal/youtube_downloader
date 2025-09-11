from flask import Flask, request, Response, redirect, url_for, render_template, flash
import yt_dlp
import subprocess
import time
import mimetypes

app = Flask(__name__)
app.secret_key = "your_secret_key"

video_cache = {}
CACHE_TIMEOUT = 3600  # 1 hour

def get_cached_video_info(url):
    current_time = time.time()
    if url in video_cache:
        info, timestamp = video_cache[url]
        if current_time - timestamp < CACHE_TIMEOUT:
            return info
    return None

def cache_video_info(url, info):
    video_cache[url] = (info, time.time())

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url").strip()
        if not url:
            flash("Please enter a YouTube URL", "danger")
            return redirect(url_for("index"))
        
        info = get_cached_video_info(url)
        if not info:
            try:
                ydl_opts = {'quiet': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    cache_video_info(url, info)
            except Exception as e:
                flash(f"Error fetching video info: {str(e)}", "danger")
                return redirect(url_for("index"))
        
        formats = info.get('formats', [])
        return render_template("select.html", video_info=info, formats=formats)
    
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download():
    url = request.form.get("url").strip()
    format_id = request.form.get("format_id")
    filename = request.form.get("filename")

    if not url or not format_id or not filename:
        flash("Invalid request", "danger")
        return redirect(url_for("index"))
    
    info = get_cached_video_info(url)
    if not info:
        try:
            ydl_opts = {'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                cache_video_info(url, info)
        except Exception as e:
            flash(f"Error fetching video info: {str(e)}", "danger")
            return redirect(url_for("index"))
    
    chosen_format = info['formats'][int(format_id)]
    filename = f"{info['title']}.{chosen_format['ext']}"
    
    ydl_cmd = [
        "yt-dlp",
        "-f", chosen_format['format_id'],
        "-o", "-",  # output to stdout
        url
    ]

    print("Running yt-dlp:", " ".join(ydl_cmd))

    def generate():
        process = subprocess.Popen(ydl_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for chunk in iter(lambda: process.stdout.read(8192), b''):
                yield chunk
        finally:
            err = process.stderr.read().decode()
            if err.strip():
                print("yt-dlp error:", err)
            process.stdout.close()
            process.stderr.close()
            process.wait()

    mimetype, _ = mimetypes.guess_type(filename)
    if not mimetype:
        mimetype = "application/octet-stream"

    headers = {
        "Content-Disposition": f"attachment; filename=\"{filename}\"",
        "Content-Type": mimetype,
        "Cache-Control": "no-cache"
    }

    return Response(generate(), headers=headers)

if __name__ == "__main__":
    app.run(debug=True)
