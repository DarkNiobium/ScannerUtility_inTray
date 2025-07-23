from pynput import keyboard
import time
import threading

# Настройки
MAX_INVALID = 6
BUFFER_TIMEOUT = 0.05  # если слишком медленно — это ввод руками

# Состояния
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

def is_russian(text):
    return any('а' <= c.lower() <= 'я' or 'А' <= c <= 'Я' for c in text)

def on_press(key):
    global buffer, last_key_time, invalid_streak

    now = time.time()
    if now - last_key_time > BUFFER_TIMEOUT:
        buffer = ''
    last_key_time = now

    try:
        if hasattr(key, 'char') and key.char:
            buffer += key.char
        elif key == keyboard.Key.enter:
            code = buffer.strip()
            debug(f"ENTER pressed. Buffer: {code!r}")

            if not code or len(code) <= 4 or len(code) == 18:
                debug("⛔ Игнор: пусто или слишком коротко")
                invalid_streak = 0
            elif is_russian(code):
                debug("⛔ Игнор: есть русские буквы")
                invalid_streak = 0
            elif now - last_key_time <= BUFFER_TIMEOUT:
                # Быстрый ввод, не SSCC и не мусор → strike
                invalid_streak += 1
                debug(f"❌ Невалидный штрихкод #{invalid_streak}: {code}")
                if invalid_streak >= MAX_INVALID:
                    invalid_streak = 0
                    threading.Thread(target=fake_scan, daemon=True).start()
            else:
                debug("⛔ Ввод медленный — не считаем")
                invalid_streak = 0

            buffer = ''
    except Exception as e:
        debug(f"⚠️ Error: {e}")

def main():
    debug("Listening for keyboard input...")
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

if __name__ == "__main__":
    main()
