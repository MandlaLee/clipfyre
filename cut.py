import subprocess

def cut_segment(src, start, end, dst, vertical=True):
    vf = "crop=ih*9/16:ih,scale=1080:1920" if vertical else "scale=-2:1920"
    cmd = [
        "ffmpeg", "-y", "-ss", str(start), "-to", str(end),
        "-i", src, "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        dst,
    ]
    subprocess.run(cmd, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
