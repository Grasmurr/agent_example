import sys
import subprocess
import json
import textwrap
import os
import shutil
from pathlib import Path
import traceback
from datetime import datetime

from webvtt import WebVTT, Caption
from vosk import Model, KaldiRecognizer, SetLogLevel

SAMPLE_RATE = 16000
WORDS_PER_LINE = 7

SetLogLevel(-1)

# Global variables for model and recognizer
model = None
rec = None

# Initialize model only once at module load time
def load_model():
    global model, rec
    
    # Create model directory if it doesn't exist
    model_path = os.getenv('VOSK_MODEL_PATH')
    if not model_path:
        model_path = '/app/vosk_models'  # Default path
    
    os.makedirs(model_path, exist_ok=True)
    print(f"Using Vosk model path: {model_path}")
    
    model_name = "vosk-model-small-ru-0.22"
    model_dir = os.path.join(model_path, model_name)
    
    try:
        # If model directory exists and has content, use it
        if os.path.exists(model_dir) and os.path.isdir(model_dir) and os.listdir(model_dir):
            print(f"Loading existing Vosk model from {model_dir}")
            model = Model(model_path=model_dir)
        else:
            # Model directory doesn't exist or is empty
            print("Downloading Vosk model...")
            # This will download to Vosk's cache directory
            model = Model(model_name=model_name, lang="ru")
            
            # Try to copy from cache to our volume
            try:
                # Check common cache locations
                cache_paths = [
                    os.path.expanduser("~/.cache/vosk"),
                    "/root/.cache/vosk",
                    "/tmp/vosk"
                ]
                
                copied = False
                for cache_path in cache_paths:
                    cached_model_dir = os.path.join(cache_path, model_name)
                    if os.path.exists(cached_model_dir) and os.path.isdir(cached_model_dir):
                        print(f"Found cached model at {cached_model_dir}, copying to {model_dir}")
                        
                        # Create model directory
                        os.makedirs(model_dir, exist_ok=True)
                        
                        # Copy files
                        for item in os.listdir(cached_model_dir):
                            src = os.path.join(cached_model_dir, item)
                            dst = os.path.join(model_dir, item)
                            if os.path.isdir(src):
                                shutil.copytree(src, dst, dirs_exist_ok=True)
                            else:
                                shutil.copy2(src, dst)
                        
                        print(f"Successfully copied model to {model_dir}")
                        copied = True
                        break
                        
                if not copied:
                    print("Could not find cached model to copy. Model will be downloaded again on next restart.")
            except Exception as e:
                print(f"Failed to copy model to volume: {e}")
                traceback.print_exc()
        
        rec = KaldiRecognizer(model, SAMPLE_RATE)
        rec.SetWords(True)
        print("Vosk model successfully initialized")
    except Exception as e:
        print(f"Error initializing Vosk model: {e}")
        traceback.print_exc()

# Load the model at module initialization
load_model()

def transcribe(file_path=None):
    """Transcribe audio file to text using Vosk"""
    if not model or not rec:
        return "Speech recognition model not initialized properly"
        
    command = ["ffmpeg", "-nostdin", "-loglevel", "quiet", "-i", sys.argv[1] if not file_path else file_path,
               "-ar", str(SAMPLE_RATE), "-ac", "1", "-f", "s16le", "-"]
    with subprocess.Popen(command, stdout=subprocess.PIPE) as process:
        results = []
        text = ''
        while True:
            data = process.stdout.read(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                results.append(rec.Result())
        results.append(rec.FinalResult())
        vtt = WebVTT()
        for _, res in enumerate(results):
            words = json.loads(res).get("result")
            if not words:
                continue

            start = timestring(words[0]["start"])
            end = timestring(words[-1]["end"])
            content = " ".join([w["word"] for w in words])

            caption = Caption(start, end, textwrap.fill(content))
            vtt.captions.append(caption)
            text += content + ' '
        if len(sys.argv) > 2:
            vtt.save(sys.argv[2])
        else:
            return text


def timestring(seconds):
    minutes = seconds / 60
    seconds = seconds % 60
    hours = int(minutes / 60)
    minutes = int(minutes % 60)
    return "%i:%02i:%06.3f" % (hours, minutes, seconds)


if __name__ == "__main__":
    if not 1 < len(sys.argv) < 4:
        print("Usage: {} audiofile [output file]".format(sys.argv[0]))
        sys.exit(1)
    transcribe()
