import argparse
import os
import sys

from .cut import FFmpegNotFoundError, cut_segment, require_ffmpeg
from .detect import detect_segments


def main():
    p = argparse.ArgumentParser(
        prog="clipfyre",
        description="Turn long videos into shorts.",
    )
    p.add_argument("input", help="input video file")
    p.add_argument("--out", default="./shorts", help="output dir")
    p.add_argument("--top", type=int, default=5, help="number of shorts")
    p.add_argument("--min", type=float, default=15, help="min short length (s)")
    p.add_argument("--max", type=float, default=60, help="max short length (s)")
    p.add_argument("--model", default="base", help="whisper model size")
    p.add_argument(
        "--captions",
        action="store_true",
        help="burn word-by-word captions into each short",
    )
    p.add_argument(
        "--no-vertical",
        action="store_false",
        dest="vertical",
        help="keep the source aspect ratio instead of reframing vertically",
    )
    p.set_defaults(vertical=True)
    args = p.parse_args()

    try:
        require_ffmpeg()
    except FFmpegNotFoundError as error:
        print(str(error), file=sys.stderr)
        return 1

    from .transcribe import transcribe

    os.makedirs(args.out, exist_ok=True)
    print(f"[1/3] transcribing {args.input} ...")
    segments = transcribe(
        args.input,
        model=args.model,
        word_timestamps=args.captions,
    )

    print("[2/3] detecting moments ...")
    picks = detect_segments(
        segments,
        top=args.top,
        min_len=args.min,
        max_len=args.max,
    )

    print(f"[3/3] cutting {len(picks)} shorts ...")
    for i, seg in enumerate(picks, 1):
        path = os.path.join(args.out, f"short_{i:02d}.mp4")
        try:
            cut_segment(
                args.input,
                seg["start"],
                seg["end"],
                path,
                vertical=args.vertical,
                captions=args.captions,
                segments=segments,
            )
        except FFmpegNotFoundError as error:
            print(str(error), file=sys.stderr)
            return 1
        print(f"  -> {path}  ({seg['end']-seg['start']:.1f}s)")

    print("done.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
