import threading
import time
import csv
import os
import tkinter as tk
from datetime import datetime
from functools import partial
from pynput import keyboard
from PIL import Image, ImageDraw
import pystray
import ctypes
import pyautogui
import numpy as np
import cv2
from tkinter import ttk
from ttkthemes import ThemedTk

# Настройки
MAX_INVALID = 6
BUFFER_TIMEOUT = 0.05
SAVE_FILE_TEMPLATE = "scanner_data_{}.csv"
CONFIG_FILE = "config.txt"
ACCOUNTS = ["Akbarjon", "Abubakr", "Abdulloh", "Guest"]
TEMPLATE_PATHS = ["template1.png", "template2.png"]

def debug_print(message):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[DEBUG {now}] {message}")

def error_print(message):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[XATO {now}] {message}")

def create_image(paused):
    color = (128, 128, 0) if paused else (0, 128, 0)
    image = Image.new('RGB', (64, 64), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, 48, 48), fill='white')
    return image

def is_russian(text):
    return any('а' <= c.lower() <= 'я' or 'А' <= c <= 'Я' for c in text)

def set_english_layout():
    try:
        layout = 0x04090409  # en-US
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        hkl = user32.LoadKeyboardLayoutW(hex(layout), 1)
        user32.ActivateKeyboardLayout(hkl, 0)
        debug_print("🌐 Раскладка переключена на EN")
    except Exception as e:
        error_print(f"Не удалось переключить раскладку: {e}")

def template_found(template_paths, threshold=0.85):
    try:
        screenshot = pyautogui.screenshot()
        screen = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        for path in template_paths:
            template = cv2.imread(path)
            if template is None:
                continue
            if screen.shape[0] < template.shape[0] or screen.shape[1] < template.shape[1]:
                continue
            result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            debug_print(f"Шаблон {path}: {max_val:.3f}")
            if max_val >= threshold:
                return True
        return False
    except Exception as e:
        error_print(f"Шаблон-сравнение: {e}")
        return False

class ScannerApp:
    def __init__(self):
        self.account = self.load_last_account()
        self.buffer = ''
        self.count = 0
        self.last_scan = ''
        self.running = True
        self.paused = False
        self.icon = None
        self.tk_window = None
        self.status_label = None
        self.stat_label = None
        self.last_key_time = 0
        self.max_delay = BUFFER_TIMEOUT
        self.invalid_streak = 0
        self.enable_fake_scan = True
        self.controller = keyboard.Controller()
        self.session_start_time = time.time()
        self.session_start_count = 0
        self.scanned_codes = set()
        self.load_data()
        self.fake_scanning = False

    def load_last_account(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    account = f.read().strip()
                    if account in ACCOUNTS:
                        return account
            except Exception as e:
                error_print(f"Akkauntni o'qishda xatolik: {e}")
        return ACCOUNTS[0]

    def save_last_account(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                f.write(self.account)
        except Exception as e:
            error_print(f"Akkauntni saqlashda xatolik: {e}")

    def get_save_file(self):
        return SAVE_FILE_TEMPLATE.format(self.account)

    def load_data(self):
        save_file = self.get_save_file()
        if os.path.exists(save_file):
            try:
                with open(save_file, newline='', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    codes = set(row[0] for row in reader if row)
                    self.scanned_codes = codes
                    self.count = len(codes)
                    self.last_scan = max(codes) if codes else ''
            except Exception as e:
                error_print(f"CSV o'qishda muammo: {e}")
        else:
            self.scanned_codes = set()
            self.count = 0
            self.last_scan = ''

    def save_data(self):
        save_file = self.get_save_file()
        try:
            with open(save_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                for code in self.scanned_codes:
                    writer.writerow([code])
        except Exception as e:
            error_print(f"CSV saqlashda xatolik: {e}")


    def fake_scan(self):
        self.fake_scanning = True
        set_english_layout()
        self.controller.type("0001")
        self.controller.press(keyboard.Key.enter)
        self.controller.release(keyboard.Key.enter)
        time.sleep(3)

        if template_found(TEMPLATE_PATHS):
            debug_print("⛔ Обнаружен шаблон — '0003' отменён")
        else:
            self.controller.type("0003")
            self.controller.press(keyboard.Key.enter)
            self.controller.release(keyboard.Key.enter)
            debug_print("✅ Отправлен '0003'")

        self.fake_scanning = False

    def on_key(self, key):
        try:
            if not self.running or self.paused or self.fake_scanning:
                return
            now = time.time()
            delay = now - self.last_key_time
            self.last_key_time = now

            if delay > self.max_delay:
                self.buffer = ''

            if hasattr(key, 'char') and key.char:
                self.buffer += key.char
            elif key == keyboard.Key.enter:
                code = self.buffer.strip()
                debug_print(f"Enter. Buffer: {code}")
                is_fast = delay <= self.max_delay

                if not code or len(code) <= 4:
                    self.invalid_streak = 0
                elif is_russian(code):
                    self.invalid_streak = 0
                elif len(code) == 18 and code.isdigit():
                    set_english_layout()
                    if code not in self.scanned_codes:
                        self.scanned_codes.add(code)
                        self.count += 1
                        self.last_scan = code
                        self.save_data()
                        debug_print(f"✅ Yangi kod: {code}. Jami: {self.count}")
                        self.update_window()
                    else:
                        debug_print(f"🔁 Takroriy kod: {code}")
                    self.invalid_streak = 0
                elif is_fast:
                    self.invalid_streak += 1
                    debug_print(f"❌ Noto'g'ri kod #{self.invalid_streak}: {code}")
                    if self.invalid_streak >= MAX_INVALID and self.enable_fake_scan:
                        self.invalid_streak = 0
                        threading.Thread(target=self.fake_scan, daemon=True).start()
                else:
                    self.invalid_streak = 0
                self.buffer = ''
        except Exception as e:
            error_print(f"Klavishani qayta ishlashda xatolik: {e}")

    def start_listening(self):
        debug_print("Klaviatura tinglanmoqda...")
        listener = keyboard.Listener(on_press=self.on_key)
        listener.start()

    def start_hotkeys(self):
        def on_activate():
            self.toggle_fake_scan(None, None)
            debug_print("🎯 Ctrl+Space → FakeScan ON/OFF")
        hotkeys = keyboard.GlobalHotKeys({'<ctrl>+<space>': on_activate})
        hotkeys.start()

    def create_window(self):
        self.tk_window = ThemedTk(theme="plastic")
        self.tk_window.title("📋 Skanner Ma'lumotlari")
        self.tk_window.geometry("400x260")
        self.tk_window.protocol("WM_DELETE_WINDOW", self.tk_window.withdraw)

        self.status_label = tk.Label(self.tk_window, font=('Consolas', 14), justify="left")
        self.status_label.pack(padx=10, pady=(10, 0), anchor="w")

        self.stat_label = tk.Label(self.tk_window, font=('Consolas', 12), justify="left")
        self.stat_label.pack(padx=10, pady=(10, 5), anchor="w")

        pause_btn = tk.Button(self.tk_window, text="⏯️ Pauza / Davom ettirish", command=self.toggle_pause)
        pause_btn.pack(pady=5)

        self.update_window()
        self.tk_window.withdraw()
        self.tk_window.mainloop()

    def update_window(self):
        if self.tk_window:
            status = f"📦 Skannerlar: {self.count}\n📌 Oxirgisi: {self.last_scan or '-'}\n👤 Akkaunt: {self.account}\n"
            status += f"{'⏸️ PAUZA' if self.paused else '▶️ FAOL'} | 🔁 FakeScan: {'ON' if self.enable_fake_scan else 'OFF'}"
            self.status_label.config(text=status)

            elapsed = max((time.time() - self.session_start_time) / 3600, 0.01)
            scans_per_hour = (self.count - self.session_start_count) / elapsed
            avg_interval = (time.time() - self.session_start_time) / max((self.count - self.session_start_count), 1)
            self.stat_label.config(text=f"📈 Soatiga: {scans_per_hour:.1f} | ⌛ Har {avg_interval:.1f} sek.")

    def toggle_pause(self):
        self.paused = not self.paused
        self.update_window()
        if self.icon:
            self.icon.icon = create_image(self.paused)

    def toggle_fake_scan(self, icon, item):
        self.enable_fake_scan = not self.enable_fake_scan
        self.update_window()
        self.update_tooltip()

    def toggle_window(self, *args):
        if self.tk_window:
            if self.tk_window.state() == 'withdrawn':
                self.tk_window.deiconify()
            else:
                self.tk_window.withdraw()

    def reset_counter(self, icon, item):
        self.scanned_codes.clear()
        self.count = 0
        self.last_scan = ''
        self.session_start_time = time.time()
        self.session_start_count = 0
        self.save_data()
        self.update_window()
        self.update_tooltip()

    def update_tooltip(self):
        if self.icon:
            self.icon.title = f"Skanner: {self.count} | Oxirgisi: {self.last_scan or '-'} | FakeScan: {'ON' if self.enable_fake_scan else 'OFF'}"

    def stop(self):
        self.running = False
        if self.tk_window:
            self.tk_window.destroy()

    def switch_account(self, icon, item=None, account_name=None):
        if account_name:
            self.account = account_name
            self.save_last_account()
            self.load_data()
            self.update_tooltip()
            self.update_window()

def create_menu(scanner: ScannerApp):
    account_items = [
        pystray.MenuItem(
            account,
            partial(scanner.switch_account, account_name=account),
            checked=lambda item, acc=account: scanner.account == acc,
            radio=True
        ) for account in ACCOUNTS
    ]
    return pystray.Menu(
        pystray.MenuItem('Akkaunt', pystray.Menu(*account_items)),
        pystray.MenuItem("Hisoblagichni reset qilish", scanner.reset_counter),
        pystray.MenuItem("FakeScan yoqish/o'chirish", scanner.toggle_fake_scan),
        pystray.MenuItem("Pauza", lambda icon, item: scanner.toggle_pause()),
        pystray.MenuItem("Oynani ko'rsat/yop", scanner.toggle_window),
        pystray.MenuItem("Chiqish", lambda icon, item: (scanner.stop(), scanner.icon.stop()))
    )

def create_icon(scanner: ScannerApp):
    icon = pystray.Icon("scanner_tray")
    icon.icon = create_image(scanner.paused)
    icon.title = "Skanner"
    icon.menu = create_menu(scanner)
    scanner.icon = icon

    def update_loop():
        while scanner.running:
            scanner.update_tooltip()
            time.sleep(1)

    threading.Thread(target=update_loop, daemon=True).start()
    icon.run()

if __name__ == "__main__":
    debug_print("📦 ScannerApp ishga tushdi...")
    app = ScannerApp()
    app.start_listening()
    app.start_hotkeys()
    threading.Thread(target=create_icon, args=(app,), daemon=True).start()
    app.create_window()
