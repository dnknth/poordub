#!/usr/bin/env python3

from poordub import *
audio = PcmAudio.sine( 880) * 2 - 9

with AudioStream().open( audio.params) as output:
    audio.play( output)
