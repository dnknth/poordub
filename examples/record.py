#!/usr/bin/env python3

from poordub import AudioStream, PcmAudio

params = PcmAudio.Params(nchannels=1, sampwidth=2, framerate=44100, nframes=0)

with AudioStream(params).open(input=True) as in_out:
    print("*** recording...")
    recording = in_out.record(3000)
    print(f"*** playing: {recording}...")
    in_out.play(recording)
    print("*** done")
