import wave
import struct
import math
import os

sample_rate = 44100
duration = 1.0 # seconds
freq1 = 800.0
freq2 = 1200.0

audio = []
for i in range(int(sample_rate * duration)):
    t = i / sample_rate
    # Alternate between freq1 and freq2 to create a siren every 0.25 seconds
    freq = freq1 if (i // (sample_rate // 4)) % 2 == 0 else freq2
    value = int(32767 * math.sin(2 * math.pi * freq * t))
    audio.append(value)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(BASE_DIR, 'static')
os.makedirs(static_dir, exist_ok=True)

wav_path = os.path.join(static_dir, 'alert.wav')
with wave.open(wav_path, 'w') as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(sample_rate)
    for value in audio:
        data = struct.pack('<h', value)
        f.writeframesraw(data)

print(f"Alert sound saved to {wav_path}")
