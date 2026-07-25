# poordub

A minimalistic [PyDub](http://pydub.com) clone, written to explore the
[`audioop`](https://docs.python.org/3/library/audioop.html) module
in the Python standard library. It implements a subset of PyDub's features.

> ⚠️ `audioop` was removed in Python 3.14 (PEP 594). For Python ≥3.14, `audioop-lts` is an additional dependency.

## `PcmAudio`

The main class. A lighter version of PyDub's `AudioSegment`:

- Supports only Wave, AIFF, and SunAudio files
- Does everything in-memory
- No fancy effects (only fades)

## Usage

### Creating audio

```python
from_file = PcmAudio.from_file("sound.wav")          # read a file
sine_wave = PcmAudio.sine(hz=440)                     # ~1s sine tone
silence   = PcmAudio.silence(millis=1000)             # 1s silence
```

### Operations

| Operation | Example | Description |
|-----------|---------|-------------|
| Concatenate | `a + b` | Append audio |
| Loop | `a * 3` | Repeat 3× |
| Slice | `a[500:2000]` | 500ms–2000ms segment |
| Length | `len(a)` | Duration in ms |
| Gain | `a - 3` | Reduce by 3 dB |
| Overlay | `a & b` | Mix (adds samples) |
| Normalize | `a.normalize(to=-0.1)` | Scale to max with headroom |
| Measure | `a.dbfs()` | Signal strength in dBFS |

### Fades

```python
a.fade_in(500)                        # fade in over 500ms
a.fade_out(500)                       # fade out over 500ms
a.cross_fade(b, 300, gap=50, threshold=-9)  # cross-fade with silence gap
```

`threshold` skips the fade if the faded portion is already quiet enough.

### Channel / format conversion

```python
a.to_mono()                           # stereo → mono
a.to_stereo()                         # mono → stereo
a.to_framerate(44100)                 # resample
a.to_sample_width(2)                  # change bit depth
```

### File I/O

```python
a.to_file("out.wav")                  # write to disk
buf = a.to_buffer()                   # write to BytesIO
```

## Playback & recording

Requires `PyAudio` (install with `pip install PyAudio`) and `portaudio`
(install with `brew`, `apt`, etc.).

```python
# Playback
with AudioStream(audio.params) as stream:
    stream.play(audio)

# Recording
with AudioStream(MONO_16KHZ).open(input=True) as stream:
    recording = stream.record(3000)
    stream.play(recording)
```

`AudioStream` presets:

```python
AudioStream.CD_AUDIO      # 2ch, 16-bit, 44100 Hz
AudioStream.MONO_16KHZ    # 1ch, 16-bit, 16000 Hz
```
