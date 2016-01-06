import serial

BAUD = 9600

ino_serial = serial.Serial('COM3', BAUD)

while True:
    char = ino_serial.read()

    if char == 's':
        print('Controller restarted')
    elif char == 't':
        print('Button pressed')
