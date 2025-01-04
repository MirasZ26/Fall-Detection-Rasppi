from machine import Pin, I2C, ADC
import utime
import MPU6050
import ssd1306
import network
import urequests
import base64
import ssl
import time
import ubinascii
import ujson

i2c_oled = I2C(1, scl=Pin(15), sda=Pin(14))
i2c_mpu = I2C(0, scl=Pin(1), sda=Pin(0))

oled_width = 128
oled_height = 64
oled = ssd1306.SSD1306_I2C(oled_width, oled_height, i2c_oled)

mpu = MPU6050.MPU6050(i2c_mpu)
mpu.wake()

pulse_pin = ADC(Pin(28))

light_fall_threshold = 1.5
heavy_fall_threshold = 2.5
high_heart_rate_threshold = 120

WIFI_SSID = 'WIFI'
WIFI_PASS = 'PASSWORD'

ACCESS_TOKEN = 'TOKEN'
GMAIL_USER = 'GMAIL'
GMAIL_PASS = 'PASSWORD'

moving_avg_window = 5        
pulse_values = []
last_pulse_time = 0
bpm = 0

def connect_to_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)
    print("Connecting to WiFi...", end="")
    while not wlan.isconnected():
        print(".", end="")
        utime.sleep(1)
    print("\nConnected to WiFi!")
    print("Network config:", wlan.ifconfig())

def send_email(to_address, subject, body):
    url = 'https://www.googleapis.com/gmail/v1/users/me/messages/send'
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    email_message = f"From: {GMAIL_USER}\r\nTo: {to_address}\r\nSubject: {subject}\r\n\r\n{body}"
    encoded_message = base64.urlsafe_b64encode(email_message.encode("utf-8")).decode("utf-8")
    message = {'raw': encoded_message}

    try:
        response = urequests.post(url, headers=headers, json=message)
        if response.status_code == 200:
            print("Email sent successfully!")
        else:
            print(f"Failed to send email. Status code: {response.status_code}, Error: {response.text}")
        response.close()
    except Exception as e:
        print("Error sending email:", e)

def detect_fall(accel):
    g_total = (accel[0]**2 + accel[1]**2 + accel[2]**2)**0.5
    if g_total > heavy_fall_threshold:
        return 'heavy'
    elif g_total > light_fall_threshold:
        return 'light'
    return None

pulse_threshold = 2000 

def calculate_bpm():
    global last_pulse_time, bpm
    current_time = utime.ticks_ms()
    current_pulse = read_smoothed_pulse()

    print(f"Current Pulse Value: {current_pulse}")  

    if current_pulse > pulse_threshold and (utime.ticks_diff(current_time, last_pulse_time) > 600):
        beat_interval = utime.ticks_diff(current_time, last_pulse_time)
        bpm = (current_pulse // beat_interval) + 40
        last_pulse_time = current_time  
        print(f"Detected valid beat. New BPM: {bpm}")
    else:
        if (utime.ticks_diff(current_time, last_pulse_time) > 2000):
            bpm = 0
            print("No beat detected. BPM reset.")

    return bpm

def read_smoothed_pulse():
    value = pulse_pin.read_u16()
    pulse_values.append(value)
    if len(pulse_values) > moving_avg_window:
        pulse_values.pop(0)
    return sum(pulse_values) // len(pulse_values)

def display_fall_status(fall_message, bpm):
    oled.fill(0)
    oled.text("Fall detection", 0, 0)
    oled.text("is on", 0, 10)
    oled.text(fall_message, 0, 30)
    oled.text(f"BPM: {bpm}", 0, 50)
    oled.show()

def push_stop_alert():
    start_time = utime.ticks_ms()
    while True:
        pulse = calculate_bpm()
        elapsed_time = utime.ticks_diff(utime.ticks_ms(), start_time)

        if pulse > 60 or elapsed_time > 10000:
            break

        oled.fill(0)
        oled.text("Push", 50, 30)
        oled.show()
        utime.sleep(1)
        
        oled.fill(0)
        oled.text("Stop", 50, 30)
        oled.show()
        utime.sleep(1)

def main():
    connect_to_wifi()
    mpu.wake()
    print(f"MPU6050 Device ID: {mpu.who_am_i()}")

    while True:
        accel = mpu.read_accel_data()
        pulse = calculate_bpm()

        print(f"Accel X: {accel[0]:.2f}, Y: {accel[1]:.2f}, Z: {accel[2]:.2f}")
        print(f"BPM: {pulse}")

        fall_type = detect_fall(accel)
        if fall_type:
            fall_message = f"{fall_type} fall detected!"  
            print(fall_message)
            display_fall_status(fall_message, pulse)
            send_email("RECEIVING EMAIL", f"{fall_type} Fall Alert", f"A {fall_type} fall has been detected!")
            if pulse < 60:
                push_stop_alert()
        else:
            display_fall_status("", pulse)

        utime.sleep(1)

if __name__ == "__main__":
    main()
