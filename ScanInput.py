from pynput import keyboard
import time
import threading

# Параметры
MAX_INVALID = 6
VALID_LENGTHS = {18, 4}
BUFFER_TIMEOUT = 0.05

# Состояние
buffer = ''
last_key_time = 0
invalid_streak = 0

controller = keyboard.Controller()

def debug(msg):
    print(f"[DEBUG {time.strftime('%H:%M:%S')}] {msg}")

def fake_scan():
    debug("Fake scan: 0001 → wait 3s → 0003")
    for char in "0001":
        controller.press(char)
        controller.release(char)
        time.sleep(0.01)
    controller.press(keyboard.Key.enter)
    controller.release(keyboard.Key.enter)

    time.sleep(3)

    for char in "0003":
        controller.press(char)
        controller.release(char)
        time.sleep(0.01)
    controller.press(keyboard.Key.enter)
    controller.release(keyboard.Key.enter)

def on_press(key):
    global buffer, last_key_time, invalid_streak

    now = time.time()
    if now - last_key_time > BUFFER_TIMEOUT:
        buffer = ''
    last_key_time = now

    try:
        if hasattr(key, 'char') and key.char and key.char.isdigit():
            buffer += key.char
        elif key == keyboard.Key.enter:
            debug(f"ENTER pressed. Buffer: {buffer}")

            if len(buffer) in VALID_LENGTHS and buffer.isdigit():
                invalid_streak = 0
                debug("Valid scan.")
            else:
                invalid_streak += 1
                debug(f"Invalid scan #{invalid_streak}")
                if invalid_streak >= MAX_INVALID:
                    invalid_streak = 0
                    threading.Thread(target=fake_scan, daemon=True).start()

            buffer = ''
    except Exception as e:
        debug(f"Error: {e}")

def main():
    debug("Listening for keyboard input...")
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

if __name__ == "__main__":
    main()
