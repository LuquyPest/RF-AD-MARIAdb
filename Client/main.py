import gc
import math
import network
import urequests as requests
import ujson as json
import time
from machine import Pin, SPI, I2C, Timer
import _thread
from mfrc522 import MFRC522
from ssd1306 import SSD1306_I2C
from env import DOOR_ID, WLAN_SSID, WLAN_PASS, SERVER_IP, SERVER_PORT

# Initialize RFID reader
reader = MFRC522(spi_id=0, sck=6, miso=4, mosi=7, cs=5, rst=22)

# Initialize I2C for the OLED display
i2c = I2C(id=0, scl=Pin(1), sda=Pin(0), freq=200000)
oled = None

# Initialize LEDs
greenled = Pin(16, Pin.OUT)
redled = Pin(21, Pin.OUT)
greenled.on(); time.sleep(0.5); greenled.off()
redled.on(); time.sleep(0.5); redled.off()

# Global variables
last_activity_time = time.time()
screensaver_active = False
screensaver_thread_running = False
inactivity_timer = Timer(-1)
SCREEN_TIMEOUT = 20

def init_oled():
    global oled
    try:
        oled = SSD1306_I2C(128, 64, i2c)
        oled.fill(0)
        oled.text("Initializing...", 0, 0)
        oled.show()
    except Exception as e:
        print("display error:", e)

def display_message(message, ip_address):
    global last_activity_time, screensaver_active, screensaver_thread_running
    last_activity_time = time.time()

    # Stop screensaver cleanly if running
    screensaver_active = False
    screensaver_thread_running = False
    time.sleep(0.05)  # Give thread time to stop

    try:
        oled.fill(0)
        oled.text(f"Door ID: {DOOR_ID}", 0, 0)
        lines = message.split("\n")
        for i, line in enumerate(lines):
            oled.text(line, 0, 20 + i * 10)
        oled.text(ip_address, 0, 57)
        oled.show()
    except Exception as e:
        print("display error:", e)
        init_oled()

def draw_circle(oled, x0, y0, radius, color):
    x = radius
    y = 0
    err = 0
    while x >= y:
        oled.pixel(x0 + x, y0 + y, color)
        oled.pixel(x0 + y, y0 + x, color)
        oled.pixel(x0 - y, y0 + x, color)
        oled.pixel(x0 - x, y0 + y, color)
        oled.pixel(x0 - x, y0 - y, color)
        oled.pixel(x0 - y, y0 - x, color)
        oled.pixel(x0 + y, y0 - x, color)
        oled.pixel(x0 + x, y0 - y, color)
        y += 1
        err += 1 + 2 * y
        if 2 * (err - x) + 1 > 0:
            x -= 1
            err += 1 - 2 * x

def screensaver():
    global screensaver_active, screensaver_thread_running
    text = "RF-AD"
    center_x, center_y = 64, 32
    radius, max_radius = 36, 64
    while screensaver_active:
        try:
            oled.fill(0)
            oled.text(text, 44, 28)
            for r in range(radius, max_radius, 5):
                draw_circle(oled, center_x, center_y, r, 1)
            oled.show()
            radius = radius + 1 if radius < max_radius else 36
            time.sleep(0.01)
        except Exception:
            break
        if time.time() - last_activity_time <= SCREEN_TIMEOUT:
            screensaver_active = False
            screensaver_thread_running = False
            break

def start_screensaver_thread():
    global screensaver_active, screensaver_thread_running
    if not screensaver_thread_running:
        screensaver_active = True
        screensaver_thread_running = True
        _thread.start_new_thread(screensaver, ())

def handle_inactivity(timer):
    if time.time() - last_activity_time > SCREEN_TIMEOUT:
        start_screensaver_thread()

def reset_inactivity_timer():
    global last_activity_time
    last_activity_time = time.time()

def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    while not wlan.isconnected():
        time.sleep(0.5)
        print("Connecting to WiFi...")
    ip_address = wlan.ifconfig()[0]
    print("Connected to WiFi:", ip_address)
    display_message("WiFi Connected", ip_address)
    test_server_connection(ip_address)
    display_message(f"Server Connected\nIP: {ip_address}", ip_address)
    time.sleep(1)

def test_server_connection(ip_address):
    while True:
        try:
            response = requests.get(f"https://{SERVER_IP}:{SERVER_PORT}/")
            if response.status_code == 200:
                print("Server connection successful")
                return
            else:
                print("Server connection failed")
                display_message(f"Server Fail\nIP: {ip_address}", ip_address)
        except Exception as e:
            print("Server connection error:", e)
            display_message(f"Server Error\n{e}\nIP: {ip_address}", ip_address)
        time.sleep(2)

def send_rfid_to_server(rfid_uid):
    try:
        url = f"https://{SERVER_IP}:{SERVER_PORT}/access"
        headers = {"Content-Type": "application/json"}
        data = {"rfid_uid": rfid_uid, "door_id": DOOR_ID}
        print("Envoi vers :", url)
        print("Payload :", data)
        response = requests.post(url, headers=headers, data=json.dumps(data))
        print("Réponse code:", response.status_code)
        print("Réponse brute:", response.text)
        return response.json()
    except Exception as e:
        print("Erreur envoi serveur :", e)
        return {"access_granted": False}

def main():
    for _ in range(3):
        try:
            init_oled()
            break
        except Exception as e:
            print("OLED init error:", e)
            time.sleep(1)

    connect_wifi(WLAN_SSID, WLAN_PASS)
    ip_address = network.WLAN(network.STA_IF).ifconfig()[0]
    display_message("Scan your tag", ip_address)
    inactivity_timer.init(period=1000, mode=Timer.PERIODIC, callback=handle_inactivity)

    while True:
        try:
            reader.init()
            (status, tag_type) = reader.request(reader.REQIDL)
            if status == reader.OK:
                (status, uid) = reader.SelectTagSN()
                if status == reader.OK:
                    reset_inactivity_timer()
                    rfid_uid = "".join(str(i) for i in uid)
                    print("RFID UID:", rfid_uid)
                    display_message("Checking...", ip_address)
                    response = send_rfid_to_server(rfid_uid)
                    if response.get("access_granted"):
                        user_upn = response.get("upn", "")
                        print("Access Granted:", user_upn)
                        display_message(f"Access Granted\n{user_upn}", ip_address)
                        greenled.on()
                    else:
                        print("Access Denied")
                        display_message("Access Denied", ip_address)
                        redled.on()
                    time.sleep(2)
                    greenled.off()
                    redled.off()
                    display_message("Scan your tag", ip_address)
            gc.collect()
        except Exception as e:
            print("Erreur RFID:", e)
            reader.init()
            display_message("Erreur lecteur", ip_address)
            time.sleep(2)

if __name__ == "__main__":
    main()
