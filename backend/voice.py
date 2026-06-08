"""
voice.py — Sage voice layer
Deepgram STT + ElevenLabs TTS for Sage analytics agent
"""
from __future__ import annotations
import os
import random
import base64
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

THINKING_PHRASES = [
    "Let me pull that data for you...",
    "Checking your dataset now...",
    "Running that analysis...",
    "Give me a moment to look at that...",
    "Digging into the numbers...",
]

def transcribe_audio(audio_bytes: bytes) -> str:
    """Send audio bytes to Deepgram and return transcript text."""
    try:
        import httpx
        import json
        response = httpx.post(
            "https://api.deepgram.com/v1/listen?model=nova-2&language=en-US&smart_format=true&punctuate=true",
            headers={
                "Authorization": f"Token {DEEPGRAM_API_KEY}",
                "Content-Type": "audio/wav",
            },
            content=audio_bytes,
            timeout=30,
        )
        data = response.json()
        transcript = data["results"]["channels"][0]["alternatives"][0]["transcript"]
        return transcript.strip() if transcript.strip() else "Could not understand audio"
    except Exception as e:
        return f"Transcription error: {str(e)}"

def _strip_markdown(text: str) -> str:
    """Remove markdown formatting before sending to TTS."""
    import re
    # Remove bold and italic
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    # Remove headers
    text = re.sub(r'#{1,6}\s+', '', text)
    # Remove bullet points
    text = re.sub(r'^\s*[-•*]\s+', '', text, flags=re.MULTILINE)
    # Remove numbered lists
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # Remove backticks
    text = re.sub(r'`{1,3}(.*?)`{1,3}', r'\1', text)
    # Clean up extra whitespace
    text = re.sub(r'\n{2,}', '. ', text)
    text = re.sub(r'\n', ' ', text)
    return text.strip()


def speak(text: str) -> Optional[str]:
    """Convert text to speech via OpenAI TTS. Returns base64 audio string."""
    try:
        import openai
        import os
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        clean_text = _strip_markdown(text)
        response = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=clean_text[:500],
        )
        audio_bytes = response.content
        return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        print(f"TTS error: {e}")
        return None

def speak_thinking() -> Optional[str]:
    """Speak a random thinking phrase while tools are running."""
    return speak(random.choice(THINKING_PHRASES))

def autoplay_audio(b64_audio: str) -> str:
    """Return HTML to autoplay base64 audio in Streamlit."""
    return f"""
        <audio autoplay style="display:none">
            <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mp3">
        </audio>
    """