#!/usr/bin/env python3

from poordub import *

params = PcmAudio.Params( nchannels=1, sampwidth=2, framerate=44100)

with AudioStream().open( params, input=True) as in_out:
    print( '*** recording...')
    recording = PcmAudio.record( in_out, 3000)
    print( '*** playing: %s...' % recording)
    recording.play( in_out)
    print( '*** done')
