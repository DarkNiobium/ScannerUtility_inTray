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
import cv2
import numpy as np
import pyautogui
import keyboard as kb
import win32gui

# Настройки
MAX_INVALID = 6
BUFFER_TIMEOUT = 0.05
SAVE_FILE_TEMPLATE = "scanner_data_{}.csv"
CONFIG_FILE = "config.txt"
ACCOUNTS = ["Akbarjon", "Abubakr", "Abdulloh", "Guest"]
TEMPLATE_PATH = "valid6.png"

ENGLISH_LAYOUT = 0x04090409

try:
    import win32api
    import win32con
except ImportError:
    win32api = None

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

def switch_to_english():
    if win32api:
        hwnd = win32gui.GetForegroundWindow()
        win32api.SendMessage(hwnd, win32con.WM_INPUTLANGCHANGEREQUEST, 0, ENGLISH_LAYOUT)
def template_found(path=TEMPLATE_PATH, threshold=0.85):
    try:
        screenshot = pyautogui.screenshot()
        screenshot = np.array(screenshot)
        screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_RGB2GRAY)
        template = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if template is None:
            error_print(f"Shablon topilmadi: {path}")
            return False
        res = cv2.matchTemplate(screenshot_gray, template, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= threshold)
        return len(loc[0]) > 0
    except Exception as e:
        error_print(f"OpenCV xatolik: {e}")
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
        kb.add_hotkey('ctrl+space', self.toggle_fake_scan_hotkey)
        self.scan_0003()
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
            with open(save_file,  'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                for code in self.scanned_codes:
                    writer.writerow([code])
        except Exception as e:
            error_print(f"CSV saqlashda xatolik: {e}")

    def scan_0003(self):
        if template_found():
            debug_print("🖼️ Shablon topildi — yuborilmoqda 0003")
            self.controller.type("0003")
            self.controller.press(keyboard.Key.enter)
            self.controller.release(keyboard.Key.enter)
            return
        else:return

    def fake_scan(self):
        self.fake_scanning = True
        self.controller.type("0001")
        self.controller.press(keyboard.Key.enter)
        self.controller.release(keyboard.Key.enter)
        time.sleep(3)
        if template_found():
            debug_print("🖼️ Shablon topildi — yuborilmoqda 0003")
            self.controller.type("0003")
            self.controller.press(keyboard.Key.enter)
            self.controller.release(keyboard.Key.enter)
        else:
            debug_print("🚫 Shablon topilmadi — 0003 yuborilmadi")
        self.fake_scanning = False

    def toggle_fake_scan_hotkey(self):
        self.enable_fake_scan = not self.enable_fake_scan
        debug_print(f"FakeScan {'yoqildi' if self.enable_fake_scan else 'o\'chirildi'}")
        self.update_tooltip()
        self.update_window()

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
                    if template_found():
                        debug_print("🖼️ Shablon topildi — yuborilmoqda 0003")
                        self.controller.type("0003")
                        self.controller.press(keyboard.Key.enter)
                        self.controller.release(keyboard.Key.enter)
                    switch_to_english()
                    if code not in self.scanned_codes:
                        self.scanned_codes.add(code)
                        self.count += 1
                        self.last_scan = code
                        self.save_data()
                        debug_print(f"✅ Yangi kod: {code}. Jami: {self.count}")
                        self.update_window()
                    else:
                        debug_print(f"🔁 Takroriy kod: {code}")
                        if template_found():
                            debug_print("🖼️ Shablon topildi — yuborilmoqda 0003")
                            self.controller.type("0003")
                            self.controller.press(keyboard.Key.enter)
                            self.controller.release(keyboard.Key.enter)
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

    def create_window(self):
        self.tk_window = tk.Tk()
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
        self.toggle_fake_scan_hotkey()

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
    debug_print("\U0001F4E6 ScannerApp ishga tushdi...")
    app = ScannerApp()
    app.start_listening()
    threading.Thread(target=create_icon, args=(app,), daemon=True).start()
    app.create_window()
