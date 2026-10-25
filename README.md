# ClipFyre 🔥

**Turn long videos into shorts that catch.**

ClipFyre takes a long video, transcribes it, finds the moments worth clipping,
and cuts them into vertical-ready shorts — automatically.

## Why

Long-form video is where the substance is. Shorts are where the reach is.
ClipFyre bridges them: point it at a 60-minute video, get back the 5–10 moments
that stand on their own.

## How it works

1. **Transcribe** — Whisper turns speech into timestamped text.
2. **Detect** — score segments for hook strength, self-containment, and energy.
3. **Cut** — ffmpeg slices the winners into 9:16 shorts.

## Quick start

```bash
git clone https://github.com/YOURNAME/clipfyre.git
cd clipfyre
pip install -r requirements.txt

# transcribe + detect + cut in one go
python -m clipfyre input.mp4 --out ./shorts --top 5
