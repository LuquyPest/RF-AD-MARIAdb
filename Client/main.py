import math
import network
import urequests as requests
import ujson as json
import time
from machine import Pin, SPI, I2C, Timer
import _thread
from mfrc522 import MFRC522
from ssd1306 import SSD1306_I2C
from env import DOOR_ID, WLAN_SSID, WLAN_SSID, WLAN_PASS, SERVER_IP, SERVER_PORT


# Initialize RFID reader
reader = MFRC522(spi_id=0, sck=6, miso=4, mosi=7, cs=5, rst=22)

# Initialize I2C for the OLED display
i2c = I2C(id=0, scl=Pin(1), sda=Pin(0), freq=200000)
oled = None

# Initialize greenLED
greenled = Pin(16, Pin.OUT)
greenled.on()
time.sleep(0.5)
greenled.off()
# Initialize redLED
redled = Pin(21, Pin.OUT)
redled.on()
time.sleep(0.5)
redled.off()

# Global variables
last_activity_time = time.time()
screensaver_active = False
screensaver_thread_running = False
inactivity_timer = Timer(-1)
SCREEN_TIMEOUT = 20


def init_oled():
    """
    Initialize the OLED display.

    This function initializes the OLED display with a width of 128 pixels, height of 64 pixels,
    and communicates over the specified I2C interface.

    ## Raises:
    - Exception: If there's an error initializing the OLED display.
    """
    global oled
    try:
        oled = SSD1306_I2C(128, 64, i2c)
        oled.fill(0)
        oled.text("Initializing...", 0, 0)
        oled.show()
    except Exception as e:
        print("display error:", e)
        # init_oled()


def display_message(message, ip_address):
    """
    Display a message on the OLED screen.

    This function displays a message on the OLED screen along with the IP address.

    ## Parameters:
        - message (str): The message to be displayed.
        - ip_address (str): The IP address to be displayed.

    ## Raises:
        - Exception: If there's an error displaying the message on the OLED screen.
    """
    global last_activity_time, screensaver_active, screensaver_thread_running
    last_activity_time = time.time()
    screensaver_active = False
    screensaver_thread_running = False
    try:
        oled.fill(0)
        oled.text(f"Door ID: {DOOR_ID}", 0, 0)  # Display Door ID at the top
        oled.text("___________________", 0, 3)

        lines = message.split("\n")
        for i, line in enumerate(lines):
            oled.text(line, 0, 20 + i * 10)  # Adjust the y position for each line
        oled.text("__________________", 0, 47)
        oled.text(ip_address, 0, 57)  # Display IP address at the bottom
        oled.show()
    except Exception as e:
        greenled.off()
        redled.off()
        print("display error:", e)
        init_oled()


# Function to draw a circle
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


# Screensaver function with circular wave animation
def screensaver():
    """
    Activate the screensaver with RF-AD animation.

    This function activates the screensaver by displaying an RF-AD animation moving across the screen.

    ## Global Variables:
        - screensaver_active (bool): Flag indicating if the screensaver is active.
        - screensaver_thread_running (bool): Flag indicating if the screensaver thread is running.
        - last_activity_time (float): Timestamp of the last activity.

    """
    global screensaver_active, screensaver_thread_running
    text = "RF-AD"
    center_x = 64  # Center horizontally
    center_y = 32  # Center vertically
    radius = 36
    max_radius = 64  # Maximum radius for the animation
    while screensaver_active:
        try:
            oled.fill(0)
            oled.text(text, 44, 28)

            # Draw expanding circles
            for r in range(radius, max_radius, 5):
                draw_circle(oled, center_x, center_y, r, 1)

            oled.show()
            radius += 1
            if radius > max_radius:
                radius = 36

            time.sleep(0.01)
        except Exception as e:
            break
        # Check for activity
        if time.time() - last_activity_time <= SCREEN_TIMEOUT:
            #oled.fill(0)
            screensaver_active = False
            screensaver_thread_running = False
            break


def start_screensaver_thread():
    """
    Start the screensaver thread if it's not already running.

    This function starts the screensaver thread if it's not already running. It sets flags to indicate
    the screensaver is active and the thread is running.

    ## Global Variables:
        - screensaver_active (bool): Flag indicating if the screensaver is active.
        - screensaver_thread_running (bool): Flag indicating if the screensaver thread is running.
    """
    global screensaver_active, screensaver_thread_running
    if not screensaver_thread_running:
        screensaver_active = True
        screensaver_thread_running = True
        _thread.start_new_thread(screensaver, ())


def handle_inactivity(timer):
    """
    Handle user inactivity by starting the screensaver if necessary.

    This function is called by a timer to check for user inactivity. If the specified time period
    has passed since the last activity, it starts the screensaver thread.

    """
    if time.time() - last_activity_time > SCREEN_TIMEOUT:
        start_screensaver_thread()


def reset_inactivity_timer():
    """
    Reset the inactivity timer.

    This function resets the last activity time to the current time, effectively restarting the
    inactivity timer.
    """
    global last_activity_time
    last_activity_time = time.time()


def test_server_connection(ip_address):
    """
    Test the connection to the server and handle connection errors.

    This function tests the connection to the server by sending an HTTP GET request to the server
    endpoint. It handles connection errors and displays appropriate messages on the OLED screen.

    ## Parameters:
        - ip_address (str): The IP address of the server.

    ## Global Variables:
        - SERVER_IP (str): The IP address of the server.
        - SERVER_PORT (int): The port number of the server.
    """
    while True:
        try:
            response = requests.get(f"http://{SERVER_IP}:{SERVER_PORT}/")
            if response.status_code == 200:
                print("Server connection successful")
                # display_message(f"Server Connected\nIP: {ip_address}", ip_address)
                return
            else:
                print("Server connection failed")
                display_message(f"Server Fail\nIP: {ip_address}", ip_address)
        except Exception as e:
            print("Server connection error:", e)
            display_message(f"Server Error\n{e}\nIP: {ip_address}", ip_address)

        # Reconnection loop
        while True:
            try:
                response = requests.get(f"http://{SERVER_IP}:{SERVER_PORT}/")
                if response.status_code == 200:
                    print("Reconnected successfully")
                    display_message(f"Server Reconnected\nIP: {ip_address}", ip_address)
                    time.sleep(1)
                    return
                display_message(f"Reconnecting...\nIP: {ip_address}", ip_address)
                time.sleep(1)
            except Exception as e:
                display_message(f"Reconnect Error\n{e}\nIP: {ip_address}", ip_address)
                time.sleep(5)


# Connect to WiFi
def connect_wifi(ssid, password):
    """
    Connect to a WiFi network.

    This function connects the device to the specified WiFi network using the provided SSID and password.
    It waits until the connection is established and then displays a message on the OLED screen indicating
    successful connection.

    ## Parameters:
        - ssid (str): The SSID of the WiFi network.
        - password (str): The password of the WiFi network.

    ## Global Variables:
        - SERVER_IP (str): The IP address of the server.
        - SERVER_PORT (int): The port number of the server.
    """
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


# Function to send RFID UID to the server
def send_rfid_to_server(rfid_uid):
    """
    Send RFID UID to the server for access verification.

    This function constructs a JSON payload containing the RFID UID and the door ID, and sends it to the server
    for access verification. It expects a JSON response from the server indicating whether access is granted.

    ## Parameters:
        - rfid_uid (str): The RFID UID to be sent to the server.

    ## Returns:
        - dict: A dictionary containing the response from the server, indicating whether access is granted.
    """
    try:
        url = f"http://{SERVER_IP}:{SERVER_PORT}/access"
        headers = {"Content-Type": "application/json"}
        data = {"rfid_uid": rfid_uid, "door_id": DOOR_ID}
        response = requests.post(url, headers=headers, data=json.dumps(data))
        #  print(response.json())
        return response.json()
    except Exception as e:
        test_server_connection(ip_address=network.WLAN(network.STA_IF).ifconfig()[0])
        return {"access_granted": False}


# Main loop to scan RFID tags
def main():
    """
    Main loop to scan RFID tags and handle access control.

    This function initializes the OLED display, connects to WiFi, and starts a loop to scan RFID tags.
    It handles user authentication by sending the RFID UID to the server and displaying access status on the OLED.

    The function also sets up an inactivity timer to activate a screensaver after 1 minute of inactivity.

    """
    # Retry mechanism for OLED initialization
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
        (status, tag_type) = reader.request(reader.REQIDL)
        if status == reader.OK:
            (status, uid) = reader.SelectTagSN()
            if status == reader.OK:
                reset_inactivity_timer()

                rfid_uid_decimal = "".join([str(i) for i in uid])
                print("RFID UID:", rfid_uid_decimal)
                display_message("Checking...", ip_address)

                response = send_rfid_to_server(rfid_uid_decimal)

                if response.get("access_granted"):
                    user_upn = response.get("upn")
                    print("Access Granted:", user_upn)
                    display_message(f"Access Granted\n{user_upn}", ip_address)
                    # Turn on the LED to indicate door open
                    greenled.on()
                    # Add code here to open the door (e.g., trigger a relay)
                else:
                    print("Access Denied")
                    display_message("Access Denied", ip_address)
                    redled.on()

                time.sleep(2)  # Delay to avoid rapid repeated reads
                greenled.off()
                redled.off()  # Turn off the LED
                display_message("Scan your tag", ip_address)


if __name__ == "__main__":
    main()
