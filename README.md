# minidub

A minimalistic [PyDub](http://pydub.com) clone.

This small package was written out of curiosity about the
[audioop](https://docs.python.org/3/library/audioop.html) module 
in the Python standard library.
It implements a subset of [PyDub's](http://pydub.com) features.

You probably should not use it, but [it works](tests.py) and illustrates
how to use [audioop](https://docs.python.org/3/library/audioop.html)
correctly.

## `PcmAudio` objects

The main (and only) class in this module is `PcmAudio`, which is a
shrink-wrapped version of PyDub's `AudioSegment`, but a bit less
capable than the original:

* Supports only file formats that Python understands, i.e. Wave, AIFF, and SunAudio.
* Does everyting in-memory
* Has no fancy audio effects (other than fades)

## Usage

To read a file from disk, use `PcmAudio.from_file(audio_file, audio_format=wave)`,
where `audio_file` can be a path or a file-like object, and `audio_format` can
be either `wave`, `aifc`, or `sunau`.

Approximately a second of a simple sine wave can be obtained with `PcmAudio.sine(hz)`,
and silence with `PcmAudio.silence(millis=0)`.

To add audio parts, use `+` like so: `part1 + part2`. To loop, multiply with the 
number of repetitions: `audio * 3`

To extract a segment from an audio clip, slice it at the desired time: `audio[start:end]`,
where `start` and `end` should be in milliseconds, defaulting to `0` and the
total audio length, respectively. The total audio length can be obtained with 
`len(audio)`.

To change the amplitude, add or subtract the desired amplitude change in
[dB](https://en.wikipedia.org/wiki/Decibel): `audio - 3`.

To overlay two audio clips, use `clip1 & clip2`, but careful: This adds the 
signals, which might result in ugly noise if the sum of amplitudes is greater than 
the maximum possible amplitude for the sample width. If that happens, add some
negative gain to the clips before overlaying them.

Also make certain that audios have the same length before overlaying them.
Otherwise, the longer part will be clipped.

A rough measure of the signal [strength](https://en.wikipedia.org/wiki/DBFS)
can be obtained with `audio.dbfs()`. If it is too low,
`audio.normalize(headroom=0.1)` will scale it to the max
with a safety margin, given in dB by `headroom`.

To write audio files, use `audio.to_file(audio_file, audio_format=wave, compression=None)`.
`audio_file` and `audio_format` are as above, and `compression` is only supported
for [AIFF](https://docs.python.org/3/library/aifc.html#aifc.aifc.setcomptype) files.

A memory buffer containing an audio file can be obtained with
`audio.to_buffer(self, audio_format=wave, compression=None)`.
To play a clip, call `audio.play()` which returns a `simpleaudio.PlayObject`.

### Fades

As stated above, the only effects are fades:

* `audio.fade_in(duration, threshold=float('-inf'))`
* `audio.fade_out(duration, threshold=float('-inf'))`
* `audio.cross_fade(other, duration, gap=0, threshold=float('-inf'))`

For these, `duration` is in milliseconds as usual, and `threshold`
is the minimum amplitude that needs to be exceeded in the portion 
being faded before the actual fade is applied.

While this sounds somewhat technical, it improves the audible 
result of cross-fades: If one part is already very low at 
the beginning or the end, it needs no additional fade,
but can be used as-is in the overlay. Try -9dB for testing this.

Finally, the `gap` is the duration (in milliseconds)
of additional silence that is inserted at each end of the 
audio parts during cross-fades. It can be used to make the transition from 
one clip to another audibly clearer.

### Misc

`audio.to_mono()` and `audio.to_stereo()` do what their names suggest.
Additionally, there are two technical operations `to_framerate()` and 
`to_sample_width()` which are used internally to ensure consistency
between clips before appending or overlaying. 

## `AudioStream`

Playback and recording use `PyAudio`, which in turn depends on the 
cross-platform `portaudio` library. It can be installed with 
`apt-get`, `brew` or similar.

The `AudioStream` wrapper is takes care of frame I/O in **blocking**
mode. The `open` method expects `PcmAudio.Params` with the desired
number of channels, sample width and frame rate. By default, it 
opens a stream in playback mode. Pass `input=True` for recording.

`AudioStream` can be used as a context manager that opens
the stream with default settings and closes it on exit.

Example code:

```python
with AudioStream( AudioStream.CD_AUDIO) as out:
    out.play( some_audio)

with AudioStream( AudioStream.MONO_16KHZ).open( input=True) as in_out:
    recording = in_out.record( 3000)
    in_out.play( recording)
```
