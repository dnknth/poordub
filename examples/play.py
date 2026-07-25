#!/usr/bin/env python3

from poordub import AudioStream, PcmAudio

audio = PcmAudio.sine(880) * 2 - 9

with AudioStream(audio.params).open() as output:
    output.play(audio)
