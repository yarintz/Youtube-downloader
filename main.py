# downloader/main.py
import os
import uuid
import shutil
import tempfile
from fastapi import FastAPI, Query, Header, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
import yt_dlp

app = FastAPI()

# Protect the endpoint with a shared API key (optional but recommended)
API_KEY = os.environ.get("DOWNLOADER_API_KEY")  # set this on the host

@app.get("/download")
def download(url: str = Query(...), background_tasks: BackgroundTasks = None, x_api_key: str = Header(None)):
    """
    Download audio from YouTube and stream it back as MP3.
    Returns 200 with an audio/mpeg streaming response on success.
    """
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not url:
        raise HTTPException(status_code=400, detail="Missing 'url' query param")

    tmp_dir = tempfile.mkdtemp(prefix="ydl_")
    unique = str(uuid.uuid4())[:8]
    outtmpl = os.path.join(tmp_dir, f"song_{unique}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": True,
        "nocheckcertificate": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # find mp3
        files = [f for f in os.listdir(tmp_dir) if f.lower().endswith(".mp3")]
        if not files:
            raise HTTPException(status_code=500, detail="Downloader created no mp3 file")

        path = os.path.join(tmp_dir, files[0])

        # ensure tmp_dir is cleaned after response is finished
        if background_tasks:
            background_tasks.add_task(shutil.rmtree, tmp_dir, ignore_errors=True)

        return StreamingResponse(open(path, "rb"), media_type="audio/mpeg",
                                 headers={"Content-Disposition": f'attachment; filename="{files[0]}"'})
    except yt_dlp.utils.DownloadError as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"yt_dlp error: {str(e)[:200]}")
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)[:200]}")
