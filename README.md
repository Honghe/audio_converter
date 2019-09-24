# Audio Converter
Simple Audio Converter.

![](art/screenshot.png)

## Requirements
- Python >=3.5 & < 3.7
- PyQt5 (4.9 is Better for fbs)
- fbs
- FFmpeg (standalone FFmpeg install in System)

## Notes
**subprocess.Popen without cmd console**
ffmpeg folder in source code is a fork of https://github.com/kkroening/ffmpeg-python with add `startupinfo` to 
```python
startupinfo = subprocess.STARTUPINFO()
startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
return subprocess.Popen(
    args, stdin=stdin_stream, stdout=stdout_stream, stderr=stderr_stream, startupinfo=startupinfo
    )
```
