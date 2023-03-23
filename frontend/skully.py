from gpiozero import Servo, LED
from gpiozero.pins.pigpio import PiGPIOFactory
from time import sleep, monotonic
import threading
import math
import random
import pasimple

JAW_PIN=13
NECK_PIN=19
PULSE_SINK='alsa_output.usb-Logitech_Logitech_G430_Gaming_Headset-00.analog-stereo.monitor'

# Audio attributes for the recording
FORMAT = pasimple.PA_SAMPLE_S32LE
SAMPLE_WIDTH = pasimple.format2width(FORMAT)
CHANNELS = 1
SAMPLE_RATE = 41000

class Neck(threading.Thread):
  def __init__(self, gpio_factory, pin):
    threading.Thread.__init__(self)
    self.thread_name = "neck_thread"
    self.thread_ID = 1000
    self.neck = Servo(pin, pin_factory = gpio_factory)
    self.neck.value = None
    self.position = 0
    self.delta = 0.05
    self.sleep_time = 0.2
    self.max = 0.5
    self.min = -0.5

  def run(self):
    steps = 10
    step_size = (abs(self.max) + abs(self.min)) / steps
    while True:
      sleep(3)
      pos = random.randrange(0, steps)
      value = self.min + (pos * step_size)
      #print(f"New value: {value}, {pos}, {step_size}")
      self.neck.value = value
      sleep(0.5)
      self.neck.value = None

  def run2(self):
    while True:
      self.neck.value = self.position
      sleep(self.sleep_time)
      self.neck.value = None
      self.position += self.delta
      if self.position > self.max or self.position < self.min:
        self.delta *= -1.0
        self.position += self.delta
      sleep(0.1)

class Jaw(threading.Thread):
  def __init__(self, gpio_factory, servo_pin, left_pin, right_pin):
    threading.Thread.__init__(self)
    self.thread_name = "jaw_thread"
    self.thread_ID = 2000
    self.servo = Servo(servo_pin, pin_factory = gpio_factory)
    self.rightEye = LED(right_pin, pin_factory=gpio_factory)
    self.leftEye = LED(left_pin, pin_factory=gpio_factory)


    self.closed = 0.45
    self.open = -0.1
    self.open_interval = 0.5
    self.open_time = 0

  def reset(self):
    self.leftEye.on()
    self.rightEye.on()
    self.servo.value = self.closed
    sleep(0.5)
    self.servo.value = None

  def close(self):
    self.servo.value = self.closed
    if monotonic() - self.open_time >= self.open_interval:
      self.rightEye.off()
      self.leftEye.off()

  def get_sample(self):
    # Record 25ms of audio
    with pasimple.PaSimple(pasimple.PA_STREAM_RECORD, FORMAT, CHANNELS, SAMPLE_RATE, device_name=PULSE_SINK) as pa:
      audio_data = pa.read(CHANNELS * SAMPLE_RATE * SAMPLE_WIDTH * 25/1000)
      return audio_data


  def speak(self, percent):
    self.open_time = monotonic()
    self.rightEye.on()
    self.leftEye.on()

    range = abs(self.open) + abs(self.closed)
    print(f"Range {range}")
    v = self.closed - range * percent * 1.5
    clamped = max(self.open, min(self.closed, v))
    self.servo.value = clamped
    print(f"Jaw Value {self.servo.value}")

  def run(self):
    print("Starting jaw!")
    while True:
      # get sample
      sleep(1)
      self.reset()
      continue

      # print the output level
      if peak_sample > 0.001:
        print(f"Output level: {peak_sample}%")
        self.speak(peak_sample)
      else:
        self.close()

factory = PiGPIOFactory()

neck_thread = Neck(factory, NECK_PIN)
#neck_thread.start()

jaw_thread = Jaw(factory, JAW_PIN, 17, 18)
jaw_thread.start()

while True:
  sleep(1)

