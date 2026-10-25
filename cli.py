import argparse, os
from .transcribe import transcribe
from .detect import detect_segments
from .cut import cut_segment

def main():
    p = argparse.ArgumentParser(prog="clipfyre",
        description="Turn long videos into shorts.")
    p.add_argument("input", help="input video file")
    p.add_argument("--out", default="./shorts", help="output dir")
    p.add_argument("--top", type=int, default=5, help="number of shorts")
    p.add_argument("--min", type=float, default=15, help="min short length (s)")
    p.add_argument("--max", type=float, default=60, help="max short length (s)")
    p.add_argument("--model", default="base", help="whisper model size")
    args = p.parse_args()

    os.makedirs(args.out, exist_ok=True)
    print(f"[1/3] transcribing {args.input} ...")
    segments = transcribe(args.input, model=args.model)

    print("[2/3] detecting moments ...")
    picks = detect_segments(segments, top=args.top,
                            min_len=args.min, max_len=args.max)

    print(f"[3/3] cutting {len(picks)} shorts ...")
    for i, seg in enumerate(picks, 1):
        path = os.path.join(args.out, f"short_{i:02d}.mp4")
        cut_segment(args.input, seg["start"], seg["end"], path)
        print(f"  -> {path}  ({seg['end']-seg['start']:.1f}s)")

    print("done.")

if __name__ == "__main__":
    main()
