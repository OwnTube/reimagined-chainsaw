"""Continuous, bounded recording of the disposable Windows test desktop."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


class DesktopRecording:
    def __init__(self, output):
        if os.name!='nt':raise RuntimeError('Windows desktop recording required')
        import imageio_ffmpeg
        self.ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
        self.output=Path(output)
        self.path=self.output/'join-recording.mp4'
        self.log=(self.output/'recording-encoder.log').open('wb')
        self.started=time.monotonic()
        self.events=[]
        self.process=subprocess.Popen([
            self.ffmpeg,'-hide_banner','-loglevel','warning','-y',
            '-f','gdigrab','-framerate','12','-draw_mouse','1','-i','desktop',
            '-t','180','-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2',
            '-c:v','libx264','-preset','ultrafast','-crf','23',
            '-pix_fmt','yuv420p','-movflags','+faststart',str(self.path)],
            stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=self.log,
            creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(0.75)
        if self.process.poll() is not None:
            self.log.close()
            raise RuntimeError('Desktop recorder did not start; inspect recording-encoder.log')
        self.event('continuous desktop capture started')

    def event(self, name):
        self.events.append({'seconds':round(time.monotonic()-self.started,3),'event':name})

    def finish(self):
        import imageio_ffmpeg
        self.event('recording stopped before peer cleanup')
        wall_seconds=time.monotonic()-self.started
        try:
            if self.process.poll() is None:
                self.process.stdin.write(b'q\n');self.process.stdin.flush()
                self.process.stdin.close()
            self.process.wait(timeout=15)
        except (OSError,subprocess.TimeoutExpired):
            self.process.kill();self.process.wait(timeout=5)
        finally:self.log.close()
        report={'validated':False,'capture':'continuous FFmpeg gdigrab of the disposable native Windows desktop',
                'edited':False,'audio':False,'events':self.events,
                'encoder_exit_code':self.process.returncode,'wall_seconds':round(wall_seconds,3)}
        try:
            if self.process.returncode!=0:raise RuntimeError('Desktop recorder exited unsuccessfully')
            reader=imageio_ffmpeg.read_frames(str(self.path))
            try:metadata=next(reader)
            finally:reader.close()
            frames,seconds=imageio_ffmpeg.count_frames_and_secs(str(self.path))
            if frames<24 or seconds<2:raise RuntimeError('Recording is too short')
            if abs(seconds-wall_seconds)>3:raise RuntimeError('Recording duration does not match the real test interval')
            report.update({'validated':True,'frames':frames,'seconds':seconds,
                           'size':list(metadata['source_size']),'fps':metadata['fps'],
                           'sha256':hashlib.sha256(self.path.read_bytes()).hexdigest(),
                           'file':'join-recording.mp4'})
        except Exception as error:report['error']=str(error)
        (self.output/'recording.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
