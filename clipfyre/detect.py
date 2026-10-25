import re

HOOK_WORDS = {
    "how", "why", "what", "never", "always", "secret", "mistake",
    "biggest", "best", "worst", "nobody", "everyone", "truth",
    "stop", "start", "should", "you", "your",
}

def _score(segment_text, length):
    words = re.findall(r"[a-z']+", segment_text.lower())
    if not words:
        return 0.0
    hook = sum(w in HOOK_WORDS for w in words) / len(words)
    # prefer 20-50s clips
    length_penalty = abs(length - 35) / 35
    return hook * 2.0 - length_penalty

def detect_segments(segments, top=5, min_len=15, max_len=60):
    """Greedy: group consecutive segments into windows, score, keep best."""
    picks, i = [], 0
    while i < len(segments):
        start = segments[i]["start"]
        text, j = [], i
        while j < len(segments) and segments[j]["end"] - start <= max_len:
            text.append(segments[j]["text"])
            j += 1
        end = segments[j-1]["end"]
        length = end - start
        if length >= min_len:
            picks.append({
                "start": start, "end": end,
                "text": " ".join(text).strip(),
                "score": _score(" ".join(text), length),
            })
        i = j if j > i else i + 1

    picks.sort(key=lambda s: s["score"], reverse=True)
    return picks[:top]
