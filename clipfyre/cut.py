import os
import re
import shutil
import subprocess
import tempfile


HIGHLIGHT_WORDS = {
    "best",
    "crazy",
    "secret",
    "money",
    "truth",
    "worst",
}
WORD_EMOJI = {"fire": "🔥"}


class FFmpegNotFoundError(RuntimeError):
    pass


def require_ffmpeg():
    if shutil.which("ffmpeg") is None:
        raise FFmpegNotFoundError("ERROR:FFMPEG_NOT_FOUND")


def _ass_words(segments, clip_start, clip_end):
    for segment in segments:
        words = segment.get("words")
        if words:
            for word in words:
                start = max(clip_start, float(word["start"]))
                end = min(clip_end, float(word["end"]))
                text = word.get("word", word.get("text", "")).strip()
                if text and end > start:
                    yield start - clip_start, end - clip_start, text
            continue

        text = segment.get("text", "").strip()
        tokens = re.findall(r"\S+", text)
        start = max(clip_start, float(segment["start"]))
        end = min(clip_end, float(segment["end"]))
        if not tokens or end <= start:
            continue
        duration = (end - start) / len(tokens)
        for index, token in enumerate(tokens):
            yield (
                start - clip_start + index * duration,
                start - clip_start + (index + 1) * duration,
                token,
            )


def write_ass_subtitles(
    segments,
    clip_start,
    clip_end,
    path,
    face_in_lower_third=False,
):
    try:
        import pysubs2
    except ImportError as error:
        raise RuntimeError("Captions require the pysubs2 package.") from error

    subtitles = pysubs2.SSAFile()
    subtitles.info["PlayResX"] = "1080"
    subtitles.info["PlayResY"] = "1920"
    subtitles.styles["Default"] = pysubs2.SSAStyle(
        fontname="Arial Black",
        fontsize=64,
        bold=True,
        outline=4,
        shadow=2,
        alignment=8 if face_in_lower_third else 2,
        marginv=150,
        primarycolor=pysubs2.Color(255, 255, 255),
        outlinecolor=pysubs2.Color(0, 0, 0),
    )

    for start, end, text in _ass_words(segments, clip_start, clip_end):
        normalized = re.sub(r"\W+", "", text).lower()
        if normalized in HIGHLIGHT_WORDS:
            text = r"{\c&H00FFFF&}" + text + r"{\c&HFFFFFF&}"
        if normalized in WORD_EMOJI:
            text += WORD_EMOJI[normalized]
        subtitles.events.append(
            pysubs2.SSAEvent(
                start=int(start * 1000),
                end=max(int(end * 1000), int(start * 1000) + 1),
                text=text,
            )
        )

    if not subtitles.events:
        return False
    subtitles.save(path)
    return True


def _escape_filter_path(path):
    for character in ("\\", "'", ":", ",", "[", "]"):
        path = path.replace(character, "\\" + character)
    return path


def cut_segment(
    src,
    start,
    end,
    dst,
    vertical=True,
    captions=False,
    segments=(),
):
    require_ffmpeg()
    vf_parts = []
    face_in_lower_third = False
    if vertical:
        from .tracker import track_faces

        tracking = track_faces(src, start, end)
        vf_parts.append(
            f"crop={tracking.crop_width}:ih:"
            f"x='{tracking.x_expression}',scale=1080:1920"
        )
        face_in_lower_third = tracking.face_in_lower_third
    else:
        vf_parts.append("scale=-2:1920")

    subtitle_path = None
    try:
        if captions:
            with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as subtitle_file:
                subtitle_path = subtitle_file.name
            has_subtitles = write_ass_subtitles(
                segments,
                start,
                end,
                subtitle_path,
                face_in_lower_third=face_in_lower_third,
            )
            if has_subtitles:
                vf_parts.append(
                    f"subtitles='{_escape_filter_path(subtitle_path)}'"
                )

        command = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-to",
            str(end),
            "-i",
            src,
            "-vf",
            ",".join(vf_parts),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            dst,
        ]
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
        )
    except FileNotFoundError as error:
        raise FFmpegNotFoundError("ERROR:FFMPEG_NOT_FOUND") from error
    finally:
        if subtitle_path and os.path.exists(subtitle_path):
            os.unlink(subtitle_path)
