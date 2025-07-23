import threading
from pynput import keyboard as pyn_keyboard
import pystray
from PIL import Image, ImageDraw
import time
import csv
import os
from functools import partial
from datetime import datetime
import tkinter as tk

SAVE_FILE_TEMPLATE = "scanner_data_{}.csv"
CONFIG_FILE = "config.txt"
ACCOUNTS = ["Akbarjon", "Abubakr", "Abdulloh", "Guest"]

def debug_print(message):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[DEBUG {now}] {message}")

def error_print(message):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[XATO {now}] {message}")

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
        self.max_delay = 0.05
        self.scanned_codes = set()
        self.session_start_time = time.time()
        self.session_start_count = 0
        self.load_data()

    def load_last_account(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    account = f.read().strip()
                    debug_print(f"Oxirgi foydalanuvchi yuklandi: {account}")
                    if account in ACCOUNTS:
                        return account
            except Exception as e:
                error_print(f"Akkauntni o'qishda xatolik: {e}")
        debug_print(f"Standart akkaunt tanlandi: {ACCOUNTS[0]}")
        return ACCOUNTS[0]

    def save_last_account(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                f.write(self.account)
            debug_print(f"Akkaunt saqlandi: {self.account}")
        except Exception as e:
            error_print(f"Akkauntni saqlashda xatolik: {e}")

    def get_save_file(self):
        return SAVE_FILE_TEMPLATE.format(self.account)

    def load_data(self):
        save_file = self.get_save_file()
        debug_print(f"Ma'lumotlar yuklanmoqda: {save_file}")
        if os.path.exists(save_file):
            try:
                with open(save_file, newline='', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    codes = set(row[0] for row in reader if row)
                    self.scanned_codes = codes
                    self.count = len(codes)
                    self.last_scan = max(codes) if codes else ''
                debug_print(f"{self.count} ta kod yuklandi. Oxirgisi: {self.last_scan}")
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
            debug_print(f"{len(self.scanned_codes)} ta kod saqlandi: {save_file}")
        except Exception as e:
            error_print(f"CSV saqlashda xatolik: {e}")

    def start_listening(self):
        def on_press(key):
            try:
                if not self.running or self.paused:
                    return

                now = time.time()
                delay = now - self.last_key_time
                self.last_key_time = now
                if delay > self.max_delay:
                    self.buffer = ''

                if hasattr(key, 'char') and key.char and key.char.isdigit():
                    self.buffer += key.char
                elif key == pyn_keyboard.Key.enter:
                    debug_print(f"Enter bosildi. Buffer: {self.buffer}")
                    if len(self.buffer) == 18 and self.buffer.isdigit():
                        if self.buffer not in self.scanned_codes:
                            self.scanned_codes.add(self.buffer)
                            self.count += 1
                            self.last_scan = self.buffer
                            debug_print(f"Yangi kod: {self.buffer}. Jami: {self.count}")
                            self.save_data()
                            self.update_window()
                        else:
                            debug_print(f"Bu kod avval kiritilgan: {self.buffer}")
                    self.buffer = ''
            except Exception as e:
                error_print(f"Klavishani qayta ishlashda xatolik: {e}")

        debug_print("Klaviatura tinglanmoqda...")
        pyn_keyboard.Listener(on_press=on_press).start()

    def create_window(self):
        self.tk_window = tk.Tk()
        self.tk_window.title("📋 Skanner Ma'lumotlari")
        self.tk_window.geometry("400x240")
        self.tk_window.protocol("WM_DELETE_WINDOW", self.tk_window.withdraw)
        self.status_label = tk.Label(self.tk_window, font=('Consolas', 14), justify="left")
        self.status_label.pack(padx=10, pady=(10, 0), anchor="w")
        self.stat_label = tk.Label(self.tk_window, font=('Consolas', 12), justify="left")
        self.stat_label.pack(padx=10, pady=(10, 5), anchor="w")
        pause_btn = tk.Button(self.tk_window, text="⏯️ Pauza / Davom ettirish", command=self.toggle_pause)
        pause_btn.pack(pady=5)
        self.session_start_time = time.time()
        self.session_start_count = self.count
        self.update_window()
        self.tk_window.withdraw()
        self.tk_window.mainloop()

    def update_window(self):
        if self.tk_window:
            self.status_label.config(text=f"📦 Skannerlar: {self.count}\n📌 Oxirgisi: {self.last_scan or '-'}\n👤 Akkaunt: {self.account}\n{'⏸️ [PAUZA]' if self.paused else '▶️ [FAOL]'}")
            elapsed = max((time.time() - self.session_start_time) / 3600, 0.01)
            scans_per_hour = (self.count - self.session_start_count) / elapsed
            avg_interval = (time.time() - self.session_start_time) / max((self.count - self.session_start_count), 1)
            self.stat_label.config(text=f"📈 Soatiga: {scans_per_hour:.1f}  |  ⌛ Har {avg_interval:.1f} sekunda")

    def toggle_pause(self):
        self.paused = not self.paused
        self.update_window()
        if self.icon:
            self.icon.icon = create_image(self.paused)

    def stop(self):
        debug_print("Dastur to‘xtatilmoqda...")
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

    def reset_counter(self, icon, item):
        self.scanned_codes = set()
        self.count = 0
        self.last_scan = ''
        self.session_start_time = time.time()
        self.session_start_count = 0
        self.save_data()
        self.update_window()
        self.update_tooltip()

    def update_tooltip(self):
        if self.icon:
            self.icon.title = f"Skannerlar soni: {self.count} | Oxirgisi: {self.last_scan or '-'} | Account: {self.account}"

    def toggle_window(self, *args):
        if self.tk_window:
            if self.tk_window.state() == 'withdrawn':
                self.tk_window.deiconify()
            else:
                self.tk_window.withdraw()

def create_image(paused):
    color = (128, 128, 0) if paused else (0, 128, 0)
    image = Image.new('RGB', (64, 64), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, 48, 48), fill='white')
    return image

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
        pystray.MenuItem("Hisoblagichni reset qilish", lambda icon, item: scanner.reset_counter(icon, item)),
        pystray.MenuItem("Pauza", lambda icon, item: scanner.toggle_pause()),
        pystray.MenuItem("Oynani ko'rsat/yop", lambda icon, item: scanner.toggle_window()),
        pystray.MenuItem("Chiqish", lambda icon, item: (scanner.stop(), scanner.icon.stop() if scanner.icon else None))
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
    debug_print("ScannerApp ishga tushdi...")
    scanner = ScannerApp()
    scanner.start_listening()
    threading.Thread(target=create_icon, args=(scanner,), daemon=True).start()
    scanner.create_window()
