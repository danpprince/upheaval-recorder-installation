from datetime import datetime
from glob import glob
import numpy
import pyaudio
from random import randint
from scipy.io import wavfile
import serial
import serial.tools.list_ports as list_ports
import time
import wave


BAUD         =  9600
AUDIO_CHUNK  =  1024
SAMPLE_RATE  = 44100

# Define recording and playing states
PLAYING   = 0
RECORDING = 1
# Initialize application state to playing
state = PLAYING

p = pyaudio.PyAudio()

# Open the audio files to be played back
wavnames = glob('./play/*.wav')

# Randomly select a file to use initially
current_file = wavnames[randint(0, len(wavnames)-1)]
rate, data = wavfile.read(current_file)
data_idx = 0


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
        rec_dev_idx = i
        break

if rec_dev_idx == -1:
    print('Error: unable to open device ' + rec_dev_name)


in_stream = p.open(format=pyaudio.paInt16,
                   channels=1,
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
    print('One serial port available, opening :' + str(port))
    port_dev_id = port.device
    ino_serial = serial.Serial(port_dev_id, BAUD)
elif port_count > 1:
    port_name = 'COM3'
    print('Multiple ports available:')
    for port in list_ports.comports():
        print(port)
    print('Opening port ' + port_name)
    ino_serial = serial.Serial(port_name, BAUD)
    
else:
    print('No ports available, please connect the Arduino')


rec_frames = []

while True:
    char = ''
    if ino_serial.in_waiting > 0:
        char = ino_serial.read()

        if char == 's':
            print('Controller restarted')
        elif char == 't':
            print('Button pressed, new state is'),

            # If state is currently PLAYING, make the new state RECORDING
            if state == PLAYING:
                state = RECORDING
                ino_serial.write('r')
                print('recording')

                in_stream.start_stream()
                out_stream.stop_stream()

            # Else if state is currently RECORDING, make the new state PLAYING
            elif state == RECORDING:
                state = PLAYING
                ino_serial.write('p')
                print('playing')

                in_stream.stop_stream()

                # Save record data in a new wave file with the current timestamp
                new_fname = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                wf = wave.open('./play/rec_' + new_fname + '.wav', 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(b''.join(rec_frames))
                wf.close()

                # Get the new list of wavfiles 
                wavnames = glob('./play/*.wav')

                rec_frames = []

                out_stream.start_stream()

    if state == RECORDING:
        # Get new audio frames from the input stream
        rec_frames.append(in_stream.read(AUDIO_CHUNK))

    elif state == PLAYING:
        # Write audio frames to the output stream
        buffer_data = data[data_idx:data_idx+AUDIO_CHUNK]
        out_stream.write(buffer_data)

        data_idx = data_idx + AUDIO_CHUNK/2

        # If the end of the current wavfile is reached, play a new file
        if data_idx >= len(data):
            # Select a new file to play next that is not the same as the current file
            new_wav_candidates = [f for f in wavnames if f != current_file]
            new_file = new_wav_candidates[randint(0, len(new_wav_candidates)-1)]
            new_rate, new_data = wavfile.read(new_file)

            current_file = new_file
            data         = new_data
            data_idx = 0
