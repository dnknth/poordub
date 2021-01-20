#!/usr/bin/env python3

import io, unittest
from poordub import *


NEG_INF = float('-inf')


class TestPcmAudio( unittest.TestCase):
    'Test audio operations.'

    # TODO: Write tests for cross_fade()


    def setUp( self):
        self.empty   = PcmAudio.silence()
        self.silence = PcmAudio.silence( 1000)
        self.sin440  = PcmAudio.sine( 440)
        self.sin880  = PcmAudio.sine( 880).adjust( AudioStream.MONO_16KHZ)


    def test_constructor( self):
        ''' The PcmAudio constructor should not be used directly.
            But it should validate its arguments.
        '''
        with self.assertRaises( PcmValueError, msg='Bad data length'):
            PcmAudio( (1, 2, 8000), b'?')
        with self.assertRaises( PcmValueError, msg='Bad frame rate'):
            PcmAudio( (1, 2, 800))
        with self.assertRaises( PcmValueError, msg='Bad number of channels'):
            PcmAudio( (0, 2, 8000))
        with self.assertRaises( PcmValueError, msg='Bad sample width'):
            PcmAudio( (1, 0, 8000, 0))


    def test_length( self):
        'Sine waves should be appx. 1 second.'
        self.assertAlmostEqual( 1, len( self.sin880) / 1000, 2) # ~1s
        self.assertAlmostEqual( 1, len( self.sin440) / 1000, 2) # ~1s
        self.assertEqual( 1000, len( self.silence)) # 1000 ms
        self.assertEqual( 0, len( self.empty)) # Nothing

        
    def test_equality( self):
        'Check equality of audio objects'
        self.assertEqual( self.sin880, self.sin880) # Identity
        
        # Different waves
        self.assertEqual( len( self.sin440[:500]), len( self.sin880[:500]))
        self.assertNotEqual( self.sin440[:500], self.sin880[:500])
        
        # Different length
        self.assertNotEqual( self.silence, self.silence[1:])

    
    def test_addition( self):
        'Check concatenation of audios with "+"'
        self.assertAlmostEqual( # Compare lengths
            (len( self.sin880) + len( self.sin440)) / 1000,
            len( self.sin880 + self.sin440) / 1000, 2)
        self.assertEqual( # Compare lengths
            len( self.sin880) + len( self.silence),
            len( self.sin880 + self.silence))

        # Adding empty has no effect
        self.assertEqual( self.sin880, self.sin880 + self.empty)
        self.assertEqual( self.sin880, self.empty + self.sin880)
        
        # Adding clips can change the frame rate and sample width
        hifi = self.sin440 + self.sin880             
        self.assertEqual( 2, hifi.params.sampwidth)
        self.assertEqual( 44100, hifi.params.framerate)
        self.assertEqual( 1, hifi.params.nchannels)

        
    def test_loop( self):
        'Check loops with "*"'
        self.assertEqual( 2 * self.sin880, self.sin880 * 2) # Swap operands
        self.assertEqual( self.empty, self.empty * 3) # Empty loop

        # Looping looks like multiplication ...
        self.assertEqual( self.sin880 + self.sin880, self.sin880 * 2)

        # ... and distributes in corner cases ...
        self.assertEqual( 2 * (self.sin880 + self.sin880),
            2 * self.sin880 + 2 * self.sin880)
        
        # ... but it does not really.
        self.assertNotEqual( 2 * (self.sin880 + self.sin440),
            2 * self.sin880 + 2 * self.sin440)
    
    
    def test_sliced_length( self):
        'Make sure that slices have the expected length in milliseconds'
        self.assertEqual( 500, len( self.sin440[:500])) # Default start
        self.assertAlmostEqual( 0.5, len( self.sin440[:-500]) / 1000, 2) # Default start
        self.assertEqual( 500, len( self.sin440[-500:])) # Default end
        self.assertEqual( 500, len( self.sin440[100:600])) # Positive range
        self.assertEqual( 500, len( self.sin440[-600:-100])) # Regative range 
        self.assertAlmostEqual( 0.5, len( self.sin440[100:-400]) / 1000, 2) # Mixed range
        
        self.assertEqual( 0, len( self.sin440[-100:-200])) # Start > end
        self.assertEqual( 0, len( self.sin440[100:100]))   # Start == end


    def test_max( self):
        'Test max plausibility'
        self.assertEqual( NEG_INF, self.silence.max(), 'Silence should be mute')
        self.assertEqual( NEG_INF, self.empty.max(),   'Empty audio should be mute')
        self.assertLess(  NEG_INF, self.sin440.max(),  'Sine waves should not be mute')
        self.assertGreater( 0, self.sin440.max(),      'max should be always negative')

        
    def test_dbfs( self):
        'Test dBFS plausibility'
        self.assertEqual( NEG_INF, self.silence.dbfs(), 'Silence should be mute')
        self.assertEqual( NEG_INF, self.empty.dbfs(),   'Empty audio should be mute')
        self.assertLess(  NEG_INF, self.sin440.dbfs(),  'Sine waves should not be mute')
        self.assertGreater( 0, self.sin440.dbfs(),      'dBFS should be always negative')

        
    def test_gain( self):
        'Run through gain changes'
        self.assertEqual( self.sin440 + 3, 3 + self.sin440) # Swap operands

        dbfs = self.sin440.dbfs()
        gained = self.sin440 - 3 # Apply -3 dB gain
        self.assertGreater( self.sin440._max(), gained._max())      # Less amplitude
        
        # dBFS changes by gained dB
        self.assertAlmostEqual( dbfs - 3, gained.dbfs(), 1)
        self.assertAlmostEqual( dbfs, (gained + 3).dbfs(), 1)       # Revert gain
        self.assertAlmostEqual( dbfs, gained.normalize().dbfs(), 0) # Normalize

        self.assertEqual( NEG_INF, (self.sin440 + NEG_INF).max())  # Mute down

        # Gain has no effect on silence 
        self.assertEqual( NEG_INF, (self.silence + 3).max())

        
    def test_overlay( self):
        'Confirm that overlays do as expected'
        
        # Swap operands
        self.assertEqual( self.sin440 & self.sin880, self.sin880 & self.sin440)
        
        # Overlaying clips the longer part
        self.assertEqual( len( self.sin440), len( self.silence & self.sin440))
        
        # Adding a longer silence should have no effect
        self.assertEqual( self.sin440, self.silence & self.sin440)
        
        # Overlaying clips adds their amplitudes
        x, y = self.sin440 - 6, self.sin880 - 6 # Prevent overflow
        self.assertGreater( (x & y)._max(), x._max())
        self.assertGreater( (x & y)._max(), y._max())

        # Overlaying clips can change the frame rate and sample width
        hifi = self.sin440 & self.sin880
        self.assertEqual( 2, hifi.params.sampwidth)
        self.assertEqual( 44100, hifi.params.framerate)
        self.assertEqual( 1, hifi.params.nchannels)
        
        
    def test_invert( self):
        self.assertEqual( NEG_INF, (self.sin440 & self.sin440.invert()).max())

        
    def test_fade( self):
        'Fade in & out. Cross fades are not tested here.'
        # Fading should not alter the length
        self.assertEqual( len( self.sin440), len( self.sin440.fade_in( 500)))
        self.assertEqual( len( self.sin440), len( self.sin440.fade_out( 500)))
        
        # But it should change the amplitude
        self.assertGreater( self.sin440[:499].dbfs(),
            self.sin440.fade_in( 500)[:499].dbfs())
        self.assertGreater( self.sin440[-499:].dbfs(),
            self.sin440.fade_out( 500)[-499:].dbfs())


    def test_mono_stereo( self):
        'Convert mono to stereo and back'
        self.assertEqual( 1, self.sin440.params.nchannels)
        stereo = self.sin440.to_stereo()
        self.assertNotEqual( self.sin440, stereo)
        self.assertEqual( 2, stereo.params.nchannels)
        self.assertEqual( self.sin440, stereo.to_mono())
        
        left, right = self.sin440._adjust_both( self.sin880)
        hifi = left[:900].to_stereo( right[:900])
        self.assertEqual( 2, hifi.params.sampwidth)
        self.assertEqual( 44100, hifi.params.framerate)

        
    def test_file_io( self):
        'Verify wave file I/O'
        with io.BytesIO() as wave_file:
            self.sin440.to_file( wave_file) # Dump to file
            
            # NB: to_buffer() is the same as above
            self.assertEqual( wave_file.getvalue(), self.sin440.to_buffer())
            
            wave_file.seek( 0)
            read_back = PcmAudio.from_file( wave_file) # Read back
            self.assertEqual( self.sin440, read_back)  # Compare


if __name__ == '__main__': unittest.main()
