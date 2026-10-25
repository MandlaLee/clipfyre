import whisper


def transcribe(path, model="base", word_timestamps=False):
    m = whisper.load_model(model)
    result = m.transcribe(
        path,
        verbose=False,
        word_timestamps=word_timestamps,
    )
    return result["segments"]
