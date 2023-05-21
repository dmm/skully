from gpiozero import Servo, LED
from gpiozero.pins.pigpio import PiGPIOFactory
from time import sleep, monotonic
import threading
import math
import random
import pyaudio
from vad import EnergyVAD
import numpy as np
from queue import Queue

from collections import deque
import audioop
import wave
import io
import requests


JAW_PIN=13
NECK_PIN=19
PULSE_SINK='alsa_output.usb-Logitech_Logitech_G430_Gaming_Headset-00.analog-stereo.monitor'

# Audio attributes for the recording
FORMAT = pyaudio.paInt16
CHANNELS = 1
SAMPLE_RATE = 16000
FRAME_LENGTH = 25 # milliseconds
FRAMES_PER_BUFFER = int((SAMPLE_RATE / 1000) * FRAME_LENGTH)


def record_on_detect(file_name, silence_limit=1, silence_threshold=2500, chunk=1024, rate=44100, prev_audio=1):
  CHANNELS = 2
  FORMAT = pyaudio.paInt16

  p = pyaudio.PyAudio()
  stream = p.open(format=p.get_format_from_width(2),
                  channels=CHANNELS,
                  rate=rate,
                  input=True,
                  output=False,
                  frames_per_buffer=chunk)

  listen = True
  started = False
  rel = rate/chunk
  frames = []

  prev_audio = deque(maxlen=int(prev_audio * rel))
  slid_window = deque(maxlen=int(silence_limit * rel))

  while listen:
    data = stream.read(chunk)
    slid_window.append(math.sqrt(abs(audioop.avg(data, 4))))

    if(sum([x > silence_threshold for x in slid_window]) > 0):
      if(not started):
        print("Starting record of phrase")
        started = True
    elif (started is True):
      started = False
      listen = False
      prev_audio = deque(maxlen=int(0.5 * rel))

    if (started is True):
      frames.append(data)
    else:
      prev_audio.append(data)

  stream.stop_stream()
  stream.close()

  p.terminate()

  print("writing...")
  wav_bytes = io.BytesIO()
  wf = wave.open(wav_bytes, 'wb')
  wf.setnchannels(CHANNELS)
  wf.setsampwidth(p.get_sample_size(FORMAT))
  wf.setframerate(rate)

  wf.writeframes(b''.join(list(prev_audio)))
  wf.writeframes(b''.join(frames))
  wf.close()

  return wav_bytes

def transcribe(wav_bytes):
  url = 'http://192.168.5.110:9000/asr?task=transcribe&output=txt'
  files = [('audio_file', ('audio.wav', wav_bytes, 'audio/x-wav'))]
  r = requests.post(url, files=files)
  print(f"TRANSCRIPTION: {r.text}")

class VoiceDetection(threading.Thread):
  voice_active = False

  def __init__(self):
    threading.Thread.__init__(self)


  def run(self):
    print("Starting voice detection thread...")
    p = pyaudio.PyAudio()
    stream = p.open(format=p.get_format_from_width(2),
                    channels=CHANNELS,
                    rate=SAMPLE_RATE,
                    input=True,
                    output=False,
                    frames_per_buffer=FRAMES_PER_BUFFER)
    vad = EnergyVAD(
      sample_rate  = 16000,
      frame_length = 25, # in milliseconds
      frame_shift = 20, # in milliseconds
      energy_threshold = 0.05, # you may need to adjust this value
      pre_emphasis = 0.95,
    )

    while True:
      wav_bytes = record_on_detect("/tmp/snake")
      wav_bytes.seek(0)
      transcribe(wav_bytes)
      continue
      data = stream.read(FRAMES_PER_BUFFER)
      buf = np.frombuffer(data, dtype=np.int16)

      active_array = vad(buf)
      print(f"Active samples: {active_array}")
      is_active = any(a for a in active_array)
      if (is_active and not self.voice_active):
        print("Voice Activated!")
      elif (not is_active and self.voice_active):
        print("Voice deactivated!")

      self.voice_active = is_active

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

  def move(self, new_position):
    diff = self.position 

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

#factory = PiGPIOFactory()

#neck_thread = Neck(factory, NECK_PIN)
#neck_thread.start()

#jaw_thread = Jaw(factory, JAW_PIN, 17, 18)
#jaw_thread.start()

voice_thread = VoiceDetection()
voice_thread.start()

while True:
  sleep(1)

