import serial
import time

BAUD = 9600

# Define recording and playing states
PLAYING   = 0
RECORDING = 1

# Initialize application state to playing
state = PLAYING

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
            print('recording')
        elif state == RECORDING:
            state = PLAYING
            ino_serial.write('p')
            print('playing')

    time.sleep(0.01)
