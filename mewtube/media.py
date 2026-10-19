"""One bounded worker; durable jobs are retried after a process restart."""
import json
import shutil
import subprocess
import threading
import time
from .store import DATA, db

MAX_SECONDS = 3600
FORMATS = 'mov,matroska,webm,avi,mpegts,ogg'


def run(args, timeout=1800):
    return subprocess.run(args, check=True, capture_output=True, timeout=timeout)


def process(video_id):
    source = DATA / 'incoming' / video_id
    target = DATA / 'media' / video_id
    target.mkdir(exist_ok=True)
    try:
        probe = json.loads(run(['ffprobe', '-v', 'error', '-format_whitelist', FORMATS, '-protocol_whitelist', 'file,pipe',
                               '-show_format', '-show_streams', '-of', 'json', str(source)], 30).stdout)
        duration = float(probe.get('format', {}).get('duration', 0))
        if not 0 < duration <= MAX_SECONDS or not any(s['codec_type'] == 'video' for s in probe['streams']):
            raise ValueError('Upload must be a video between 0 and 3600 seconds.')
        # Restrict demuxer protocols: uploaded playlists cannot fetch network/internal URLs.
        run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-threads', '2', '-format_whitelist', FORMATS, '-protocol_whitelist', 'file,pipe',
             '-i', str(source), '-map', '0:v:0', '-map', '0:a:0?', '-sn', '-dn',
             '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2',
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p',
             '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(target / 'video.mp4')])
        run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(target / 'video.mp4'),
             '-frames:v', '1', '-vf', 'scale=640:-1', str(target / 'thumb.jpg')], 60)
        with db() as c:
            c.execute("UPDATE videos SET status='ready', duration=?,size=?,error=NULL WHERE id=?",
                      (duration, (target / 'video.mp4').stat().st_size, video_id))
    except Exception as e:
        shutil.rmtree(target, ignore_errors=True)
        # Do not expose local paths or untrusted ffmpeg stderr in API responses.
        message = str(e) if isinstance(e, ValueError) else 'Video processing failed; check format and server FFmpeg installation.'
        with db() as c:
            c.execute("UPDATE videos SET status='failed',error=? WHERE id=?", (message, video_id))
    finally:
        source.unlink(missing_ok=True)


def start_worker():
    # A process restart cannot resume an interrupted HTTP request body.
    with db() as c:
        incomplete = c.execute("SELECT id FROM videos WHERE status='uploading'").fetchall()
        for row in incomplete:
            (DATA / 'incoming' / row['id']).unlink(missing_ok=True)
        c.execute("UPDATE videos SET status='failed',error='Upload interrupted; upload the file again.' WHERE status='uploading'")
    def worker():
        while True:
            with db() as c:
                row = c.execute("SELECT id FROM videos WHERE status='processing' ORDER BY created LIMIT 1").fetchone()
            if row:
                process(row['id'])
            else:
                time.sleep(1)
    thread = threading.Thread(target=worker, daemon=True, name='transcode')
    thread.start()
    return thread
