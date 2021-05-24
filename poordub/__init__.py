import audioop, atexit, io, itertools, sys, wave
from array import array
from collections import namedtuple
from math import log, pi, sin


__all__ = ( 'AudioStream', 'PcmAudio', 'PcmValueError' )
__version__ = '0.1.2'


MUTE = float( '-inf')


def db_to_ratio( db):
    'Translate a (negative) dB value into a scaling ratio'
    return 10 ** (float( db) / 20)


def ratio_to_db( ratio):
    'Translate a scaling ratio into negative dB'
    return MUTE if ratio <= 0 else 20 * log( float( ratio), 10)


def sign( x):
    'Obtain the sign of a number, one of {-1, 0, 1}'
    return (x > 0) - (x < 0)


class PcmValueError( ValueError):
    'PcmAudio error, a subclass of `ValueError`'
    pass


class PcmAudio:
    ''' Poor man's PyDub, manipulates raw audio data in-memory.
        
        Most operations produce new audio objects:
        * Applying gain: Add / subtract the desired number of dB, (`audio - 3`)
        * Concatenating: Add audios (i.e. `audio1 + audio2`)
        * Looping: Multiply, (i.e. `audio * 3`)
        * Extracting segments: Slice by the desired number of milliseconds,
          (i.e. `audio[:5000]` for first 5s, or `audio[-5000:]` for the last 5s)
    '''
    
    class Params( namedtuple( 'pcm_params',
        'nchannels sampwidth framerate nframes')):
        
        FRAME_RATES = ( 8000, 11025, 16000, 22050, 24000, 32000,
                       44100, 48000, 88200, 96000, 192000 )
        
        
        def __init__( self, *args, **kw):
            if self.nchannels not in (1, 2):
                raise PcmValueError(
                    'Illegal number of channels: %d' % self.nchannels)
            if self.sampwidth not in (1, 2, 3, 4):
                raise PcmValueError(
                    'Illegal sample width: %d' % self.sampwidth)
            if self.framerate not in self.FRAME_RATES:
                raise PcmValueError(
                    'Illegal frame rate: %d' % self.framerate)
            if self.nframes < 0:
                raise PcmValueError(
                    'Illegal number of frames: %d' % self.nframes)


        def match( self, other):
            'Same number of channels, sample witdth and frame rate?'
            return ( self.nchannels == other.nchannels
                 and self.sampwidth == other.sampwidth
                 and self.framerate == other.framerate)
        
        
        @property
        def frame_size( self):
            'Number of bytes in each frame'
            return self.sampwidth * self.nchannels
    
    
        @property
        def scale( self):
            'Maximum signed amplitude for the given sample width'
            bits = self.sampwidth * 8
            return int( (2 ** bits) / 2)
    
    
        @classmethod
        def max( cls, *args):
            'Maximise the number of channels, sample witdth and frame rate'
            return cls(
                max( map( lambda p: p[0], args)),
                max( map( lambda p: p[1], args)),
                max( map( lambda p: p[2], args)), 0)
    
    
    def __init__( self, params, frames=b'',
        nchannels=None, sampwidth=None, framerate=None, nframes=None):
        ''' Construct a PcmAudio from raw data.
            :param params: audio parameters (nchannels, sampwidth, framerate, nframes)
            :param frames: raw audio data in system byte order.
            Keyword args override values in params.
        '''
        
        if nframes is None:
            nframes = 0 if len( params) < 4 else params[3]

        self.params = self.Params(
            nchannels if nchannels is not None else params[0],
            sampwidth if sampwidth is not None else params[1],
            framerate if framerate is not None else params[2],
            nframes)
        
        if self.params.frame_size * nframes != len( frames):
            raise PcmValueError( 'Illegal frame data length: %d, expected: %d'
                % (len( frames), self.params.frame_size * nframes))
        
        self.frames = frames
    
    
    def __str__( self):
        return "%s(channels=%d, duration=%.2fs)" % (
            self.__class__.__name__, self.params.nchannels, len( self) / 1000)
    
    
    def __len__( self):
        'Length of audio in milliseconds'
        return round( self.params.nframes / self.params.framerate * 1000)
    
    
    def __eq__( self, other):
        if not isinstance( other, PcmAudio): return False
        return self.params == other.params and self.frames == other.frames
    
    
    def __hash__( self):
        return hash( self.params) ^ hash( self.frames)
    
    
    def __getitem__( self, millis):
        'Extract frames at milliseconds; supports slicing.'
        if isinstance( millis, slice):
            if millis.step:
                raise PcmValueError( 'Only continuous slicing is supported')
            start = 0 if millis.start is None else millis.start
            stop  = len( self) + 1 if millis.stop is None else millis.stop
        else:
            start, stop = millis, millis + 1
        
        return self._slice(
            round( start * self.params.framerate / 1000),
            round( stop  * self.params.framerate / 1000))
    
    
    def _slice( self, start=0, stop=None):
        'Extract frames by index.'
        nframes = self.params.nframes
        if abs( start) > nframes: start = nframes * sign( start)
        if stop is None: stop = nframes
        elif abs( stop) > nframes: stop = nframes * sign( stop)

        if start < 0: start = start % nframes
        if stop  < 0: stop  = stop  % nframes
        if start > stop: start = stop
        
        return self.__class__( self.params,
            self.frames[ start * self.params.frame_size : stop * self.params.frame_size],
            nframes = stop - start)
    
    
    def __add__( self, other):
        'Apply gain, or concatenate two audios'
        if isinstance( other, (int, float)):
            if other == 0: return self
            return self._gain( db_to_ratio( other))
        
        if not isinstance( other, PcmAudio): return NotImplemented
        
        if other.params.nframes == 0: return self
        if self.params.nframes == 0: return other
        
        this, other = self._adjust_both( other)
        return self.__class__( this.params, this.frames + other.frames,
            nframes=this.params.nframes + other.params.nframes)


    def __radd__( self, rarg):
        'Allow use of sum() for audios'
        return self + rarg
    
    
    def join( self, iterable):
        'Join segments by interleaving this audio'
        parts = []
        for part in iterable:
            if parts: parts.append( self)
            parts.append( part)
        return sum( parts)

        
    def __sub__( self, db):
        'Apply negative gain'
        return self + (-db) \
            if isinstance( db, (int, float)) else NotImplemented
    
    
    def __mul__( self, n):
        'Loop the audio `n` times'
        if not isinstance( n, int): return NotImplemented
        if n < 1: return self.__class__.silence()
        if n == 1: return self
        return self.__class__( self.params, self.frames * n,
            nframes=self.params.nframes * n)
    
    
    def __rmul__(self, n):
        'Loop the audio `n` times'
        return self * n
    
    
    def __and__( self, other):
        'Overlay two audios, adding each sample'
        if not isinstance( other, PcmAudio): return NotImplemented
        
        this, other = self._adjust_both( other)
        nframes = min( this.params.nframes, other.params.nframes)
        
        return self.__class__( this.params, audioop.add(
            this._slice( 0, nframes).frames,
            other._slice( 0, nframes).frames,
            this.params.sampwidth), nframes=nframes)
    
    
    def _gain( self, factor):
        'Multiply the amplitude by the given factor.'
        if not self.frames: return self # empty clip
        return self.__class__( self.params,
            audioop.mul( self.frames, self.params.sampwidth, factor))
    
    
    def to_mono( self):
        'Convert stereo audio to mono'
        if self.params.nchannels == 1: return self
        return self.__class__( self.params,
            audioop.tomono( self.frames, self.params.sampwidth, 0.5, 0.5),
            nchannels=1)
    
    
    def to_stereo( self, right=None):
        'Convert mono audio to stereo'
        if right is None: right = self
        if self.params.nchannels != 1 or right.params.nchannels != 1:
            raise PcmValueError( 'Mono audio required')
        
        if self.params.framerate != right.params.framerate:
            raise PcmValueError( 'Channels have different frame rate')
        
        if self.params.nframes != right.params.nframes:
            raise PcmValueError( 'Channels have different length')
        
        left, right = self._adjust_both( right)
        
        return self.__class__( left.params, audioop.add(
                audioop.tostereo( left.frames, left.params.sampwidth, 1, 0),
                audioop.tostereo( right.frames, right.params.sampwidth, 0, 1),
            left.params.sampwidth), nchannels=2)
    
    
    def to_sample_width( self, sampwidth):
        'Convert to a new sample width'
        if self.params.sampwidth == sampwidth: return self
        if sampwidth not in (1, 2, 3, 4):
            raise PcmValueError( 'Illegal sample width: %d' % sampwidth)
        
        return self.__class__( self.params,
            audioop.lin2lin( self.frames, self.params.sampwidth, sampwidth),
            sampwidth=sampwidth)
    
    
    def to_framerate( self, framerate):
        'Convert to a new frame rate'
        if self.params.framerate == framerate: return self
        
        if framerate not in self.Params.FRAME_RATES:
            raise PcmValueError( 'Illegal frame rate: %s' % framerate)
        
        frames, _state = audioop.ratecv( self.frames, self.params.sampwidth,
                self.params.nchannels, self.params.framerate, framerate, None)
        return self.__class__( (self.params.nchannels, self.params.sampwidth,
            framerate, int( len(frames) / self.params.frame_size)), frames)
    
    
    def adjust( self, params):
        ''' Adjust to desired number of channels,
            sample width and framerate.
        '''
        this = self
        if this.params.nchannels != params.nchannels:
            if params.nchannels == 1: this = this.to_mono()
            elif params.nchannels == 2: this = this.to_stereo()
        if this.params.sampwidth != params.sampwidth:
            this = this.to_sample_width( params.sampwidth)
        if this.params.framerate != params.framerate:
            this = this.to_framerate( params.framerate)
        return this
    
    
    def _adjust_both( self, other):
        ''' Adjust two clips to the common maximum
            number of channels, sample width and framerate.
        '''
        params = self.Params.max( self.params, other.params)
        return self.adjust( params), other.adjust( params)

        
    def _max( self):
        return audioop.max( self.frames, self.params.sampwidth)
    
    
    def max( self):
        'The absolute maximum amplitude of the audio in dB'
        return ratio_to_db( self._max() / self.params.scale)
    
        
    def dbfs( self):
        'Decibels relative to full scale'
        rms = audioop.rms( self.frames, self.params.sampwidth)
        return ratio_to_db( rms / self.params.scale)
    
    
    def invert( self):
        'Invert all samples'
        return self._gain( -1)
        
    
    def normalize( self, to=-0.1):
        'Normalize the audio to the given (negative dB) amplitude.'
        peak = self._max()
        if peak == 0: return self # silence cannot be normalized
        if to > 0: raise PcmValueError( 'Negative dB value expected')
        target_peak = self.params.scale * db_to_ratio( to)
        return self._gain( target_peak / peak)
    
    
    def _fade( self, from_db=0, to_db=0):
        if from_db == to_db: return self
        
        if len( self) < 100: step_size = 1 # frame by frame
        else: step_size = round( self.params.framerate / 1000) # one ms
        steps = round( self.params.nframes / step_size)
        
        from_amp = db_to_ratio( from_db)
        step_amp = (db_to_ratio( to_db) - from_amp) / steps
        
        def get_part( step):
            start = step * step_size
            return self._slice( start, start + step_size)._gain(
                from_amp + step * step_amp)
        
        return sum( map( get_part, range( steps + 1)))
    
    
    def fade_in( self, duration, threshold=MUTE):
        ''' Fade in over a given number of milliseconds
            :param duration: Milliseconds for the cross-fade
            :param threshold: Do not fade if a part is below the given dBFS, e.g. -10
        '''
        lead_in = self[ :duration]
        if lead_in.dbfs() <= threshold: return self
        return lead_in._fade( MUTE, 0) + self[ duration:]
    
    
    def fade_out( self, duration, threshold=MUTE):
        ''' Fade out over a given number of milliseconds
            :param duration: Milliseconds for the cross-fade
            :param threshold: Do not fade if a part is below the given dBFS, e.g. -10
        '''
        lead_out = self[ -duration:]
        if lead_out.dbfs() <= threshold: return self
        return self[ :-duration] + lead_out._fade( 0, MUTE)
    
    
    def cross_fade( self, other, duration, gap=0, threshold=MUTE):
        ''' Cross-fade two audios.
            :param duration: Milliseconds for the cross-fade
            :param gap: Add this many ms of silence to each part
            :param threshold: Do not fade parts if dBFS is below the given amount, e.g. -10
        '''
        left, right = self._adjust_both( other)
        silence = self.__class__.silence( gap)._adjust( left)
        lead_out = left[ -duration:].fade_out( duration, threshold) + silence
        lead_in  = silence + right[ :duration].fade_in( duration, threshold)
        return left[ :-duration] + (lead_out & lead_in) + right[ duration:]


    def chunks( self, nframes):
        'Split raw frame data into chunks of `nframes` frames'
        step = nframes * self.params.frame_size
        for start in range( 0, len( self.frames), step):
            yield self.frames[ start : start + step]
    
    
    def _flip_sign( self):
        'Flip between signed and unsigned single byte samples'
        if self.params.sampwidth != 1: return self
        return self.__class__( self.params, audioop.bias( self.frames, 1, 0x80))


    @classmethod
    def silence( cls, millis=0):
        'Produce silence of a given length'
        nframes = round( cls.Params.FRAME_RATES[0] * millis / 1000)
        params = ( 1, 1, cls.Params.FRAME_RATES[0], nframes )
        return cls( params, bytearray( nframes))
    

    @classmethod
    def sine( cls, hz=440):
        'Produce nearly 1s of a 0dB sine wave with the given frequency'
        framerate = cls.Params.FRAME_RATES[6]
        nframes = round( framerate / hz) * hz
        frames = array( 'h',
            (round( 0x7fff * sin( 2 * pi * hz * frame / framerate))
            for frame in range( nframes)))
        return cls( (1, 2, framerate, nframes), frames.tobytes())
    
    
    @classmethod
    def from_file( cls, audio_file, audio_format=wave):
        ''' Read an audio file.
            :param audio_file: Path to audio file, or a file-like object
            :param audio_format: Python module to read audio data,
                one of wave, aifc, or sunau.
        '''
        with audio_format.open( audio_file, 'rb') as audio:
            params = audio.getparams()
            frames = audio.readframes( params.nframes)
            if audio_format is wave and params.sampwidth == 1:
                frames = audioop.bias( frames, 1, 0x80)
            if audio_format is not wave and sys.byteorder == 'little':
                frames = audioop.byteswap( frames, params.sampwidth)
            return cls( params, frames)
    
    
    def to_file( self, audio_file, audio_format=wave, compression=None):
        ''' Write an audio file.
            :param audio_file: Path to audio file, or a file-like object
            :param audio_format: Python module to write audio data,
                one of wave, aifc, or sunau.
        '''
        with audio_format.open( audio_file, 'wb') as audio:
            audio.setnchannels( self.params.nchannels)
            audio.setsampwidth( self.params.sampwidth)
            audio.setframerate( self.params.framerate)
            audio.setnframes(   self.params.nframes)
            if compression: audio.setcomptype( compression)
            frames = self.frames
            if audio_format is wave:
                frames = self._flip_sign().frames
            elif sys.byteorder == 'little':
                frames = audioop.byteswap( frames, self.params.sampwidth)
            audio.writeframesraw( frames)
    
    
    def to_buffer( self, audio_format=wave, compression=None):
        'Write file contents to a memory buffer.'
        audio_file = io.BytesIO()
        self.to_file( audio_file, audio_format, compression)
        return audio_file.getvalue()


class AudioStream:
    ''' Wraps a PyAudio stream for playback or recording.
        Requires PulseAudio, PyAudio is imported on demand.
    '''
    
    CHUNK_SIZE = 1024
    PY_AUDIO   = None
    
    # Common presets
    MONO_16KHZ = PcmAudio.Params( 1, 2, 16000, 0)
    CD_AUDIO   = PcmAudio.Params( 2, 2, 44100, 0)
    
    
    def __init__( self, params=None):
        ''' Initialize the stream and PyAudio.
            If no parameters are given,
            the output device defaults are used.
        '''
        if self.PY_AUDIO is None:
            import pyaudio
            self.__class__.PY_AUDIO = pyaudio.PyAudio()
            atexit.register( self.PY_AUDIO.terminate)
        self.stream = None
        if params:
            self.params = PcmAudio.Params( *params)
        else:
            self.params = self._get_device_params()

    
    def _get_device_params( self):
        'Obtain default parameters from the output device'
        device_info = self.PY_AUDIO.get_default_output_device_info()
        return PcmAudio.Params(
            device_info['maxOutputChannels'], 2,
            int( device_info['defaultSampleRate']), 0)
        
    
    def __str__( self):
        return "%s(channels=%d, framerate=%d)" % (
            self.__class__.__name__,
            self.params.nchannels,
            self.params.framerate)


    def __enter__( self):
        'Open the stream if needed'
        return self.open() if not self.stream else self

        
    def open( self, input=False, output=True,
        input_device_index=None, output_device_index=None):
        'Open a stream for I/O.'
        
        if self.stream:
            raise PcmValueError( 'Stream is already open')
        
        self.stream = self.PY_AUDIO.open(
            format = self.PY_AUDIO.get_format_from_width( self.params.sampwidth),
            channels = self.params.nchannels,
            rate = self.params.framerate,
            input = input, output = output,
            input_device_index = input_device_index,
            output_device_index = output_device_index,
            frames_per_buffer = self.CHUNK_SIZE)
        return self


    def _check( self):
        'Ensure that my stream is open'
        if not self.stream: raise PcmValueError( 'Stream is closed')

        
    def play( self, audio):
        'Play an audio in blocking mode.'
        self._check()
        audio = audio.adjust( self.params)._flip_sign()
        for chunk in audio.chunks( self.CHUNK_SIZE):
            self.stream.write( chunk)

    
    def record( self, milliseconds):
        'Record an audio clip in blocking mode'
        self._check()
        nframes = round( self.params.framerate * milliseconds / 1000)
        frames = bytearray( nframes)
        for frame in range( 0, nframes, self.CHUNK_SIZE):
            part = self.stream.read( min( nframes - frame, self.CHUNK_SIZE))
            start = frame * self.params.frame_size
            frames[ start : start + len( part)] = part
        return PcmAudio( self.params, frames, nframes=nframes)._flip_sign()
    
    
    def __exit__( self, type, value, traceback):
        'Safely close the stream.'
        self.close()
    
    
    def close( self):
        'Close the stream.'
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.stream = None


if __name__ == '__main__': # Demo code
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument( 'infile',  type=argparse.FileType('rb'),
        help='Input file')
    parser.add_argument( 'outfile', type=argparse.FileType('wb'),
        help='Output file')
    parser.add_argument( '-n', '--normalize', action='store_true',
        help='Normalize input')
    parser.add_argument( '-m', '--mono', action='store_true',
        help='Convert output to mono')
    parser.add_argument( '-g', '--gain', type=float,
        help='Add gain to output (in dB)')
    parser.add_argument( '-%', '--volume', dest='gain',
        help='Add gain to output (in %%)',
        type=lambda percent: ratio_to_db( int( percent) / 100))
    
    options = parser.parse_args()
    pcm = PcmAudio.from_file( options.infile)
    if options.normalize: pcm = pcm.normalize()
    if options.gain: pcm = pcm + options.gain
    if options.mono: pcm = pcm.to_mono()
    pcm.to_file( options.outfile)
