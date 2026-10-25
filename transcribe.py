import whisper

def transcribe(path, model="base"):
    m = whisper.load_model(model)
    result = m.transcribe(path, verbose=False)
    # -> [{"start":..,"end":..,"text":..}, ...]
    return result["segments"]
