import numpy
import pyaudio
from scipy.io import wavfile
import serial
import time


BAUD = 9600

# Define recording and playing states
PLAYING   = 0
RECORDING = 1
# Initialize application state to playing
state = PLAYING

p = pyaudio.PyAudio()

# Open the audio file for playing
wavname = 'DC_Break30_165.wav'
rate, data = wavfile.read(wavname)
data_idx = 0


# Define callback for playing audio
def callback(in_data, frame_count, time_info, status):
    global data_idx
    buffer_data = data[data_idx:data_idx+frame_count]
    data_idx = data_idx + frame_count

    # Reshape the buffer data to interleave frames
    out_data = buffer_data.reshape(buffer_data.size)

    return (out_data, pyaudio.paContinue)

# Open stream using callback
stream = p.open(format=pyaudio.paInt16,
                channels=data.shape[1],
                rate=rate,
                output=True,
                stream_callback=callback)

# Start the audio out stream
stream.start_stream()
ino_serial = serial.Serial('COM3', BAUD)

while True:
    char = ''
    if ino_serial.in_waiting > 0:
        char = ino_serial.read()

    if char == 's':
        print('Controller restarted')
    elif char == 't':
        print('Button pressed, new state is'),

        if state == PLAYING:
            state = RECORDING
            ino_serial.write('r')
            stream.stop_stream()
            print('recording')
        elif state == RECORDING:
            state = PLAYING
            ino_serial.write('p')
            stream.start_stream()
            print('playing')

    time.sleep(0.01)
