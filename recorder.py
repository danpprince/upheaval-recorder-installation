from datetime import datetime
from glob import glob
import logging as log
import numpy
import os
from os.path import basename
import pyaudio
from random import randint
from scipy.io import wavfile
import serial
import serial.tools.list_ports as list_ports
import sys
import time
import wave


# Communication rate constant for Arduino
BAUD =  9600

# Audio data constants
AUDIO_CHUNK  =  1024
SAMPLE_RATE  = 44100

# Set a constant size for the recently played queue in order to control
# the number of played recordings that must occur before a single recording
# should be played again
RECENTLY_PLAYED_LEN = 5

# Set a maximum time in seconds for recordings to ensure that many recordings
# are able to be cycled through in a short amount of time
MAX_REC_TIME = 45

# Set the directory for recordings to be read from and written to
REC_DIR = 'play/'

# Define recording and playing states
PLAYING   = 0
RECORDING = 1
# Initialize application state to playing
state = PLAYING

# Initialize starting timestamp
start_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

# Save recorded data in a new wave file with the current timestamp
def save_new_file(frames):
    timestamp_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    new_fname = REC_DIR + 'rec_' + timestamp_str + '.wav'
    log.info('Saving new recording ' + basename(new_fname))

    # Convert frames to an array of 16b singed integers
    data = numpy.fromstring(b''.join(frames), 'Int16')

    # Sum stereo channels to mono
    mono_data = (data[0::2] + data[1::2])/2

    # Remove the last half second of the recording to avoid the sound of
    # the button clicking
    mono_data = mono_data[:-SAMPLE_RATE/2]

    # Normalize new recordings so they can be played back at an even level
    NORM_FACTOR_LIMIT = 10
    norm_factor = pow(2, 15) / max(abs(mono_data))
    if norm_factor > NORM_FACTOR_LIMIT:
        norm_factor = NORM_FACTOR_LIMIT

    log.debug('Saving using normalization factor ' + str(norm_factor))
    wavfile.write(new_fname, SAMPLE_RATE, mono_data*norm_factor) 

    return new_fname

# Set up logger
logger = log.getLogger()
logger.setLevel(log.DEBUG)
log_filepath = 'log/'
if not os.path.exists(log_filepath):
    os.makedirs(log_filepath)

# Create file handler for logger
file_handler = log.FileHandler(log_filepath + start_timestamp + '.log')
file_handler.setLevel(log.DEBUG)
format_string = '[%(asctime)s - %(levelname)s] %(message)s'
formatter = log.Formatter(format_string)
file_handler.setFormatter(formatter)
file_handler.setLevel(log.DEBUG)
logger.addHandler(file_handler)

# Create stream handler to print messages to stdout
stream_handler = log.StreamHandler(sys.stdout)
format_string = '[%(levelname)s] %(message)s'
formatter = log.Formatter(format_string)
stream_handler.setFormatter(formatter)
stream_handler.setLevel(log.INFO)
logger.addHandler(stream_handler)

log.info('Initializing application')
log.info('Initializing PyAudio')
p = pyaudio.PyAudio()

# Open the audio files to be played back
log.info('Initializing audio queue')
wavnames = [basename(f) for f in glob(REC_DIR + '*.wav')]
log.debug('Recordings in queue: ' + str(wavnames))

# Randomly select a file to use initially
current_file = wavnames[randint(0, len(wavnames)-1)]
rate, data = wavfile.read(REC_DIR + current_file)

data_idx = 0
log.info('Randomly selected ' + current_file + ' for first in queue')

# Initialize queue lists
recently_played_files = []
up_next_files         = []

# Maintain the recently played file queue
recently_played_files.append(current_file)
log.debug('File ' + current_file + ' appended to recently played queue')


# Open stream for playing back recordings using blocking API
out_stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=SAMPLE_RATE,
                    output=True,
                    frames_per_buffer=AUDIO_CHUNK)

# Open stream for recording from microphone using blocking API
rec_dev_name = 'Input 1/2 (Komplete Audio 6 WDM'
rec_dev_idx = -1

for i in range(p.get_device_count()):
    if rec_dev_name in p.get_device_info_by_index(i)['name']:
        log.info('Opening input interface ' + rec_dev_name)
        rec_dev_idx = i
        break

if rec_dev_idx == -1:
    log.error('Unable to open device ' + rec_dev_name)


in_stream = p.open(format=pyaudio.paInt16,
                   channels=2,
                   rate=SAMPLE_RATE,
                   input=True,
                   input_device_index=rec_dev_idx,
                   frames_per_buffer=AUDIO_CHUNK)

# Start the audio out stream
out_stream.start_stream()

# List the available serial ports, pick automatically if only one avaliable
port_count = sum([1 for _ in list_ports.comports()]) 
if port_count == 1:
    port = next(list_ports.comports())
    log.info('One serial port available, opening ' + str(port))
    port_dev_id = port.device
    ino_serial = serial.Serial(port_dev_id, BAUD)
elif port_count > 1:
    port_name = 'COM3'
    log.info('Multiple ports available:')
    for port in list_ports.comports():
        log.info(port)
    log.info('Opening port ' + port_name)
    ino_serial = serial.Serial(port_name, BAUD)
else:
    log.error('No ports available, please connect the Arduino')
    exit()


rec_frames = []

log.info('Application started! ^_^')

while True:
    char = ''
    if ino_serial.in_waiting > 0:
        char = ino_serial.read()

        if char == 's':
            log.info('Controller restarted')
        elif char == 't':

            # If state is currently PLAYING, make the new state RECORDING
            if state == PLAYING:
                log.info('Button pressed, new state is recording')
                state = RECORDING
                ino_serial.write('r')

                # Pause for one second to eliminate sound from button press
                time.sleep(0.5)

                log.debug('Starting in stream, stopping out stream')
                in_stream.start_stream()
                out_stream.stop_stream()

            # Else if state is currently RECORDING, make the new state PLAYING
            elif state == RECORDING:
                log.info('Button pressed, new state is playing')
                state = PLAYING
                ino_serial.write('p')

                log.debug('Stopping in stream')
                in_stream.stop_stream()

                new_fname = save_new_file(rec_frames)

                # Play this newly recorded file next
                up_next_files.append(basename(new_fname))

                # Get the new list of wavfiles 
                wavnames = [basename(f) for f in glob(REC_DIR + '*.wav')]

                rec_frames = []

                log.debug('Starting out stream')
                out_stream.start_stream()

    if state == RECORDING and len(rec_frames)*AUDIO_CHUNK > SAMPLE_RATE*MAX_REC_TIME:
        # End the current recording if it is greater than the max record time
        log.info('Recording timeout, max time of ' + str(MAX_REC_TIME) + ' reached')
        state = PLAYING
        ino_serial.write('p')

        log.debug('Stopping in stream')
        in_stream.stop_stream()

        new_fname = save_new_file(rec_frames)

        # Play this newly recorded file next
        up_next_files.append(basename(new_fname))

        # Get the new list of wavfiles 
        wavnames = [basename(f) for f in glob(REC_DIR + '*.wav')]

        rec_frames = []

        log.debug('Starting out stream')
        out_stream.start_stream()


    elif state == RECORDING:
        # Get new audio frames from the input stream
        rec_frames.append(in_stream.read(AUDIO_CHUNK))

    elif state == PLAYING:
        # Write audio frames to the output stream
        buffer_data = data[data_idx:data_idx+AUDIO_CHUNK]
        out_stream.write(buffer_data)

        data_idx = data_idx + AUDIO_CHUNK/2

        # If the end of the current wavfile is reached, play a new file
        if data_idx >= len(data):
            log.debug('File ' + current_file + ' finished playing')

            # If a newly recorded file has been created and added to the up next
            # queue, play it now
            if len(up_next_files) > 0:
                log.debug('Newly recorded files in queue ' + str(up_next_files))
                new_file = up_next_files.pop(0)
                log.info('Playing newly recorded file ' + new_file)

            # If nothing in up next queue, select a new file that has not
            # been played recently
            else:
                new_wav_candidates = [f for f in wavnames if f not in recently_played_files]
                log.debug('Next recording candidates: ' + str(new_wav_candidates))
                new_file = new_wav_candidates[randint(0, len(new_wav_candidates)-1)]
                log.info('Playing ' + new_file)

            # Maintain the recently played file queue
            recently_played_files.append(new_file)
            log.debug('File ' + new_file + ' appended to recently played queue')

            if len(recently_played_files) > RECENTLY_PLAYED_LEN:
                least_recent_file = recently_played_files.pop(0)
                log.debug('File ' + least_recent_file + ' removed from recently played queue')

            log.debug('New recently played files queue: ' + str(recently_played_files))

            try:
                new_rate, new_data = wavfile.read(REC_DIR + new_file)
            except IOError as e:
                log.error(e)
                log.error('File ' + new_file + ' not found, continuing to next loop iteration')
                continue

            current_file = new_file
            data         = new_data
            data_idx = 0
