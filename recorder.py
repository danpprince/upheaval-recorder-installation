import numpy
import pyaudio
from scipy.io import wavfile
import serial
import time
import wave


BAUD         = 9600
RECORD_CHUNK = 1024

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

    # If the end of the data is reached, read from the beginning
    if buffer_data.size/2 < frame_count:
        needed_samples = frame_count - buffer_data.size/2
        buffer_data = numpy.concatenate((buffer_data, data[0:needed_samples]))

    data_idx = (data_idx+frame_count) % (data.size/2)

    # Reshape the buffer data to interleave frames
    out_data = buffer_data.reshape(buffer_data.size)

    return (out_data, pyaudio.paContinue)

# Open stream for playing back recordings using callback
out_stream = p.open(format=pyaudio.paInt16,
                    channels=data.shape[1],
                    rate=rate,
                    output=True,
                    stream_callback=callback)

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
                   rate=44100,
                   input=True,
                   input_device_index=rec_dev_idx,
                   frames_per_buffer=RECORD_CHUNK)

# Start the audio out stream
out_stream.start_stream()
ino_serial = serial.Serial('COM3', BAUD)

rec_frames = []
rec_name_idx = 0

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
                print('recording')

                in_stream.start_stream()
                out_stream.stop_stream()

            elif state == RECORDING:
                state = PLAYING
                ino_serial.write('p')
                print('playing')

                in_stream.stop_stream()

                # Save record data in a new wave file
                wf = wave.open('./rec/' + str(rec_name_idx) + '.wav', 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(44100)
                wf.writeframes(b''.join(rec_frames))
                wf.close()

                rec_frames = []
                rec_name_idx = rec_name_idx + 1

                out_stream.start_stream()

    if state == RECORDING:
        rec_frames.append(in_stream.read(RECORD_CHUNK))
    else:
        time.sleep(0.01)
