#!/usr/bin/env python3

import io
import unittest

from poordub import MUTE, AudioStream, PcmAudio, PcmValueError, db_to_ratio, ratio_to_db


class TestPcmAudio(unittest.TestCase):
    "Test audio operations."

    # TODO: Write tests for cross_fade()

    EMPTY = PcmAudio.silence()
    SILENCE = PcmAudio.silence(1000)
    SINE_440 = PcmAudio.sine(440)
    SINE_880 = PcmAudio.sine(880).adjust(AudioStream.MONO_16KHZ)

    def test_constructor(self):
        """The PcmAudio constructor should not be used directly.
        But it should validate its arguments.
        """
        with self.assertRaises(PcmValueError, msg="Bad data length"):
            PcmAudio((1, 2, 8000), b"?")
        with self.assertRaises(PcmValueError, msg="Bad frame rate"):
            PcmAudio((1, 2, 800))
        with self.assertRaises(PcmValueError, msg="Bad number of channels"):
            PcmAudio((0, 2, 8000))
        with self.assertRaises(PcmValueError, msg="Bad sample width"):
            PcmAudio((1, 0, 8000, 0))

    def test_length(self):
        "Sine waves should be appx. 1 second."
        self.assertAlmostEqual(1, len(self.SINE_880) / 1000, 2)  # ~1s
        self.assertAlmostEqual(1, len(self.SINE_440) / 1000, 2)  # ~1s
        self.assertEqual(1000, len(self.SILENCE))  # 1000 ms
        self.assertEqual(0, len(self.EMPTY))  # Nothing

    def test_equality(self):
        "Check equality of audio objects"
        self.assertEqual(self.SINE_880, self.SINE_880)  # Identity

        # Different waves
        self.assertEqual(len(self.SINE_440[:500]), len(self.SINE_880[:500]))
        self.assertNotEqual(self.SINE_440[:500], self.SINE_880[:500])

        # Different length
        self.assertNotEqual(self.SILENCE, self.SILENCE[1:])

    def test_addition(self):
        'Check concatenation of audios with "+"'
        self.assertAlmostEqual(  # Compare lengths
            (len(self.SINE_880) + len(self.SINE_440)) / 1000,
            len(self.SINE_880 + self.SINE_440) / 1000,
            2,
        )
        self.assertEqual(  # Compare lengths
            len(self.SINE_880) + len(self.SILENCE),
            len(self.SINE_880 + self.SILENCE),
        )

        # Adding empty has no effect
        self.assertEqual(self.SINE_880, self.SINE_880 + self.EMPTY)
        self.assertEqual(self.SINE_880, self.EMPTY + self.SINE_880)

        # Adding clips can change the frame rate and sample width
        hifi = self.SINE_440 + self.SINE_880
        self.assertEqual(2, hifi.params.sampwidth)
        self.assertEqual(44100, hifi.params.framerate)
        self.assertEqual(1, hifi.params.nchannels)

    def test_loop(self):
        'Check loops with "*"'
        self.assertEqual(2 * self.SINE_880, self.SINE_880 * 2)  # Swap operands
        self.assertEqual(self.EMPTY, self.EMPTY * 3)  # Empty loop

        # Looping looks like multiplication ...
        self.assertEqual(self.SINE_880 + self.SINE_880, self.SINE_880 * 2)

        # ... and distributes in corner cases ...
        self.assertEqual(
            2 * (self.SINE_880 + self.SINE_880),
            2 * self.SINE_880 + 2 * self.SINE_880,
        )

        # ... but it does not really.
        self.assertNotEqual(
            2 * (self.SINE_880 + self.SINE_440),
            2 * self.SINE_880 + 2 * self.SINE_440,
        )

    def test_sliced_length(self):
        "Make sure that slices have the expected length in milliseconds"
        self.assertEqual(500, len(self.SINE_440[:500]))  # Default start
        self.assertAlmostEqual(
            0.5, len(self.SINE_440[:-500]) / 1000, 2
        )  # Default start
        self.assertEqual(500, len(self.SINE_440[-500:]))  # Default end
        self.assertEqual(500, len(self.SINE_440[100:600]))  # Positive range
        self.assertEqual(500, len(self.SINE_440[-600:-100]))  # Negative range
        self.assertAlmostEqual(
            0.5, len(self.SINE_440[100:-400]) / 1000, 2
        )  # Mixed range

        self.assertEqual(0, len(self.SINE_440[-100:-200]))  # Start > end
        self.assertEqual(0, len(self.SINE_440[100:100]))  # Start == end

    def test_max(self):
        "Test max plausibility"
        self.assertEqual(MUTE, self.SILENCE.max(), "Silence should be mute")
        self.assertEqual(MUTE, self.EMPTY.max(), "Empty audio should be mute")
        self.assertLess(MUTE, self.SINE_440.max(), "Sine waves should not be mute")
        self.assertGreater(0, self.SINE_440.max(), "max should be always negative")

    def test_dbfs(self):
        "Test dBFS plausibility"
        self.assertEqual(MUTE, self.SILENCE.dbfs(), "Silence should be mute")
        self.assertEqual(MUTE, self.EMPTY.dbfs(), "Empty audio should be mute")
        self.assertLess(MUTE, self.SINE_440.dbfs(), "Sine waves should not be mute")
        self.assertGreater(0, self.SINE_440.dbfs(), "dBFS should be always negative")

    def test_gain(self):
        "Run through gain changes"
        self.assertEqual(self.SINE_440 + 3, 3 + self.SINE_440)  # Swap operands

        dbfs = self.SINE_440.dbfs()
        gained = self.SINE_440 - 3  # Apply -3 dB gain
        self.assertGreater(self.SINE_440._max(), gained._max())  # Less amplitude

        # dBFS changes by gained dB
        self.assertAlmostEqual(dbfs - 3, gained.dbfs(), 1)
        self.assertAlmostEqual(dbfs, (gained + 3).dbfs(), 1)  # Revert gain
        self.assertAlmostEqual(dbfs, gained.normalize().dbfs(), 0)  # Normalize

        self.assertEqual(MUTE, (self.SINE_440 + MUTE).max())  # Mute down

        # Gain has no effect on silence
        self.assertEqual(MUTE, (self.SILENCE + 3).max())

    def test_overlay(self):
        "Confirm that overlays do as expected"

        # Swap operands
        self.assertEqual(self.SINE_440 & self.SINE_880, self.SINE_880 & self.SINE_440)

        # Overlaying clips the longer part
        self.assertEqual(len(self.SINE_440), len(self.SILENCE & self.SINE_440))

        # Adding a longer silence should have no effect
        self.assertEqual(self.SINE_440, self.SILENCE & self.SINE_440)

        # Overlaying clips adds their amplitudes
        x, y = self.SINE_440 - 6, self.SINE_880 - 6  # Prevent overflow
        self.assertGreater((x & y)._max(), x._max())
        self.assertGreater((x & y)._max(), y._max())

        # Overlaying clips can change the frame rate and sample width
        hifi = self.SINE_440 & self.SINE_880
        self.assertEqual(2, hifi.params.sampwidth)
        self.assertEqual(44100, hifi.params.framerate)
        self.assertEqual(1, hifi.params.nchannels)

    def test_invert(self):
        self.assertEqual(MUTE, (self.SINE_440 & self.SINE_440.invert()).max())

    def test_fade(self):
        "Fade in & out. Cross fades are not tested here."
        # Fading should not alter the length
        self.assertEqual(len(self.SINE_440), len(self.SINE_440.fade_in(500)))
        self.assertEqual(len(self.SINE_440), len(self.SINE_440.fade_out(500)))

        # But it should change the amplitude
        self.assertGreater(
            self.SINE_440[:499].dbfs(),
            self.SINE_440.fade_in(500)[:499].dbfs(),
        )
        self.assertGreater(
            self.SINE_440[-499:].dbfs(),
            self.SINE_440.fade_out(500)[-499:].dbfs(),
        )

    def test_mono_stereo(self):
        "Convert mono to stereo and back"
        self.assertEqual(1, self.SINE_440.params.nchannels)
        stereo = self.SINE_440.to_stereo()
        self.assertNotEqual(self.SINE_440, stereo)
        self.assertEqual(2, stereo.params.nchannels)
        self.assertEqual(self.SINE_440, stereo.to_mono())

        left, right = self.SINE_440._adjust_both(self.SINE_880)
        hifi = left[:900].to_stereo(right[:900])
        self.assertEqual(2, hifi.params.sampwidth)
        self.assertEqual(44100, hifi.params.framerate)

    def test_file_io(self):
        "Verify wave file I/O"
        with io.BytesIO() as wave_file:
            self.SINE_440.to_file(wave_file)  # Dump to file

            # NB: to_buffer() is the same as above
            self.assertEqual(wave_file.getvalue(), self.SINE_440.to_buffer())

            wave_file.seek(0)
            read_back = PcmAudio.from_file(wave_file)  # Read back
            self.assertEqual(self.SINE_440, read_back)  # Compare

    def test_to_sample_width(self):
        "Convert sample widths"
        widened = self.SINE_440.to_sample_width(4)
        self.assertEqual(4, widened.params.sampwidth)
        self.assertEqual(len(self.SINE_440), len(widened))
        self.assertAlmostEqual(self.SINE_440.dbfs(), widened.dbfs(), 1)

        # Round-trip back to 16-bit is lossless
        self.assertEqual(self.SINE_440, widened.to_sample_width(2))
        # No-op when the width already matches
        self.assertEqual(self.SINE_440, self.SINE_440.to_sample_width(2))
        # Illegal width
        with self.assertRaises(PcmValueError):
            self.SINE_440.to_sample_width(5)

    def test_to_framerate(self):
        "Convert frame rates"
        resampled = self.SINE_440.to_framerate(22050)
        self.assertEqual(22050, resampled.params.framerate)
        self.assertAlmostEqual(1, len(resampled) / 1000, 2)  # Duration kept

        # No-op when the rate already matches
        self.assertEqual(self.SINE_440, self.SINE_440.to_framerate(44100))
        # Illegal rate
        with self.assertRaises(PcmValueError):
            self.SINE_440.to_framerate(800)

    def test_adjust(self):
        "Adjust channels, sample width and framerate at once"
        target = PcmAudio.Params(2, 4, 48000, 0)
        adjusted = self.SINE_440.adjust(target)
        self.assertEqual(2, adjusted.params.nchannels)
        self.assertEqual(4, adjusted.params.sampwidth)
        self.assertEqual(48000, adjusted.params.framerate)
        # Duration is preserved
        self.assertAlmostEqual(
            len(self.SINE_440) / 1000, len(adjusted) / 1000, 2
        )

    def test_chunks(self):
        "Split frame data into fixed-size chunks"
        chunks = list(self.SINE_440.chunks(1024))
        # All but the last chunk are exactly 1024 frames
        for chunk in chunks[:-1]:
            self.assertEqual(1024 * self.SINE_440.params.frame_size, len(chunk))
        # Chunks reassemble into the full frame data
        self.assertEqual(self.SINE_440.frames, b"".join(chunks))
        # Empty audio has no chunks
        self.assertEqual([], list(self.EMPTY.chunks(1024)))

    def test_samples(self):
        "Expose raw samples as an array"
        samples = self.SINE_440.samples()
        self.assertEqual(self.SINE_440.params.nframes, len(samples))
        self.assertEqual("h", samples.typecode)  # 16-bit signed
        self.assertEqual(0, samples[0])  # Sine starts at zero

        # 4-byte samples use C int (4 bytes), not long
        self.assertEqual(4, self.SINE_440.to_sample_width(4).samples().itemsize)

        # 8-bit samples are signed bytes
        silence = self.SILENCE.samples()
        self.assertEqual("b", silence.typecode)
        self.assertEqual(0, silence[0])

    def test_join(self):
        "Interleave a clip between several others"
        joined = self.SINE_440.join([self.SINE_880, self.SINE_880])
        # SINE_880 + SINE_440 + SINE_880
        self.assertEqual(self.SINE_880 + self.SINE_440 + self.SINE_880, joined)

        # Joining a single clip is just that clip
        self.assertEqual(self.SINE_880, self.SINE_440.join([self.SINE_880]))

    def test_cross_fade(self):
        "Overlap two clips with a cross-fade"
        cf = self.SINE_440.cross_fade(self.SINE_880, 500)
        # Overlap of 500 ms, so shorter than the sum of both
        self.assertLess(len(cf), len(self.SINE_440) + len(self.SINE_880))
        self.assertAlmostEqual(
            (len(self.SINE_440) + len(self.SINE_880) - 500) / 1000,
            len(cf) / 1000,
            2,
        )
        # Both clips are adjusted to a common format
        self.assertEqual(44100, cf.params.framerate)

        # A gap adds silence to each part
        gapped = self.SINE_440.cross_fade(self.SINE_880, 500, gap=100)
        self.assertGreater(len(gapped), len(cf))


class TestConversions(unittest.TestCase):
    "Test the dB conversion helpers."

    def test_db_to_ratio(self):
        self.assertEqual(1, db_to_ratio(0))
        self.assertEqual(0.1, db_to_ratio(-20))
        self.assertAlmostEqual(0.501187, db_to_ratio(-6), 5)

    def test_ratio_to_db(self):
        self.assertEqual(MUTE, ratio_to_db(0))
        self.assertEqual(MUTE, ratio_to_db(-1))
        self.assertEqual(0, ratio_to_db(1))
        self.assertEqual(-20, ratio_to_db(0.1))

    def test_roundtrip(self):
        self.assertAlmostEqual(-6, ratio_to_db(db_to_ratio(-6)), 5)


class TestParams(unittest.TestCase):
    "Test the audio parameter tuple."

    def test_max(self):
        params = PcmAudio.Params.max(
            PcmAudio.Params(1, 2, 44100, 0),
            PcmAudio.Params(2, 2, 44100, 0),
        )
        self.assertEqual(PcmAudio.Params(2, 2, 44100, 0), params)

    def test_match(self):
        base = PcmAudio.Params(1, 2, 44100, 100)
        self.assertTrue(base.match(PcmAudio.Params(1, 2, 44100, 200)))
        self.assertFalse(base.match(PcmAudio.Params(2, 2, 44100, 200)))

    def test_validation(self):
        with self.assertRaises(PcmValueError):
            PcmAudio.Params(3, 2, 44100, 0)
        with self.assertRaises(PcmValueError):
            PcmAudio.Params(1, 5, 44100, 0)
        with self.assertRaises(PcmValueError):
            PcmAudio.Params(1, 2, 800, 0)
        with self.assertRaises(PcmValueError):
            PcmAudio.Params(1, 2, 44100, -1)


if __name__ == "__main__":
    unittest.main()
