import threading
import time
import csv
import os
import tkinter as tk
from datetime import datetime
from functools import partial
from pynput import keyboard
from PIL import Image, ImageDraw, ImageGrab
import pystray
import cv2
import numpy as np
import pyautogui
import keyboard as kb
import win32gui

from tkinter import ttk, messagebox

# Настройки
MAX_INVALID = 6
BUFFER_TIMEOUT = 0.05
SAVE_FILE_TEMPLATE = "scanner_data_{}.csv"
CONFIG_FILE = "config.txt"
ACCOUNTS = ["Akbarjon", "Abubakr", "Abdulloh", "Guest"]
TEMPLATE_VALID6 = "valid6.png"
TEMPLATE_PRE0001 = "pre0001.png"
TEMPLATE_EXIT = "exit_button.png"

ENGLISH_LAYOUT = 0x04090409

try:
    import win32api
    import win32con
except ImportError:
    win32api = None

search_area = None

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

def safe_template_found(template_path, retries=3, delay=0.4, **kwargs):
    for _ in range(retries):
        if template_found(template_path, **kwargs):
            return True
        time.sleep(delay)
    return False

def template_found(template_path, threshold=0.85, use_area=False):
    try:
        global search_area
        screenshot = pyautogui.screenshot(region=search_area) if use_area and search_area else pyautogui.screenshot()
        screenshot_np = np.array(screenshot)
        screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)
        template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
        if template is None:
            error_print(f"Shablon topilmadi: {template_path}")
            return False
        res = cv2.matchTemplate(screenshot_gray, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        if max_val >= threshold:
            if template_path == TEMPLATE_VALID6:
                search_area = (*max_loc, template.shape[1] + 20, template.shape[0] + 20)
            return True
        return False
    except Exception as e:
        error_print(f"OpenCV xatolik: {e}")
        return False

def locate_and_click_button(template_path, threshold=0.75):
    try:
        screenshot = ImageGrab.grab()
        screenshot_np = np.array(screenshot)
        screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_BGR2GRAY)
        template = cv2.imread(template_path, 0)
        w, h = template.shape[::-1]
        result = cv2.matchTemplate(screenshot_gray, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        if max_val >= threshold:
            x, y = max_loc
            center_x, center_y = x + w // 2, y + h // 2
            pyautogui.moveTo(center_x, center_y)
            pyautogui.click()
            return True
        return False
    except Exception as e:
        error_print(f"Klick xatolik: {e}")
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
        kb.add_hotkey('ctrl+space', self.toggle_fake_scan_hotkey)
        threading.Thread(target=self.exit_button_watcher, daemon=True).start()

    def load_last_account(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except: pass
        return ACCOUNTS[0]

    def save_last_account(self):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            f.write(self.account)

    def get_save_file(self):
        return SAVE_FILE_TEMPLATE.format(self.account)

    def load_data(self):
        save_file = self.get_save_file()
        if os.path.exists(save_file):
            with open(save_file, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                self.scanned_codes = {row[0] for row in reader if row}
                self.count = len(self.scanned_codes)
                self.last_scan = max(self.scanned_codes) if self.scanned_codes else ''

    def save_data(self):
        with open(self.get_save_file(), 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for code in self.scanned_codes:
                writer.writerow([code])

    def fake_scan(self):
        self.controller.type("0001")
        self.controller.press(keyboard.Key.enter)
        self.controller.release(keyboard.Key.enter)
        time.sleep(3)
        if template_found(TEMPLATE_VALID6, use_area=True):
            self.controller.type("0003")
            self.controller.press(keyboard.Key.enter)
            self.controller.release(keyboard.Key.enter)

    def toggle_fake_scan_hotkey(self):
        self.enable_fake_scan = not self.enable_fake_scan
        debug_print(f"FakeScan {'yoqildi' if self.enable_fake_scan else 'o\'chirildi'}")
        self.update_tooltip()
        if self.tk_window:
            self.tk_window.after(0, self.update_window)

    def on_key(self, key):
        if not self.running or self.paused:
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
            debug_print(f"Buffer: {code}")
            global search_area
            search_area = None
            if not code or len(code) <= 4:
                self.invalid_streak = 0
            elif is_russian(code):
                self.invalid_streak = 0
            elif len(code) == 18 and code.isdigit():
                if template_found(TEMPLATE_PRE0001,threshold = 0.9):
                    self.controller.type("0001")
                    self.controller.press(keyboard.Key.enter)
                    self.controller.release(keyboard.Key.enter)
                    time.sleep(0.5)
                    if safe_template_found(TEMPLATE_VALID6, use_area=False):
                        self.controller.type("0003")
                        self.controller.press(keyboard.Key.enter)
                        self.controller.release(keyboard.Key.enter)
                switch_to_english()
                if code not in self.scanned_codes:
                    self.scanned_codes.add(code)
                    self.count += 1
                    self.last_scan = code
                    self.save_data()
                    debug_print(f"Yangi kod: {code}")
                    self.update_window()
                else:
                    debug_print(f"Takroriy kod: {code}")
            elif delay <= self.max_delay:
                self.invalid_streak += 1
                if self.invalid_streak >= MAX_INVALID and self.enable_fake_scan:
                    self.invalid_streak = 0
                    threading.Thread(target=self.fake_scan, daemon=True).start()
            else:
                self.invalid_streak = 0
            self.buffer = ''

    def exit_button_watcher(self):
        while True:
            time.sleep(2)
            locate_and_click_button(TEMPLATE_EXIT, threshold=0.75)

    def start_listening(self):
        listener = keyboard.Listener(on_press=self.on_key)
        listener.start()

    def create_window(self):
        self.tk_window = tk.Tk()
        self.tk_window.title("📋 Skanner Ma'lumotlari")
        self.tk_window.geometry("400x260")

        self.status_label = ttk.Label(self.tk_window, font=('Consolas', 14), anchor="w", justify="left")
        self.status_label.pack(padx=10, pady=(10, 0), anchor="w")

        self.stat_label = ttk.Label(self.tk_window, font=('Consolas', 12), anchor="w", justify="left")
        self.stat_label.pack(padx=10, pady=(10, 5), anchor="w")

        pause_btn = ttk.Button(self.tk_window, text="⏯️ Pauza / Davom ettirish", command=self.toggle_pause)
        pause_btn.pack(pady=5)

        self.update_window()
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
    debug_print("📦 ScannerApp ishga tushdi...")
    app = ScannerApp()
    app.start_listening()
    threading.Thread(target=create_icon, args=(app,), daemon=True).start()
    app.create_window()
