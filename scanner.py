import threading
from pynput import keyboard as pyn_keyboard
import pystray
from PIL import Image, ImageDraw
import time
import csv
import os
import ctypes
from functools import partial
from datetime import datetime

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
        debug_print("Dastur boshlanmoqda...")
        self.account = self.load_last_account()
        self.buffer = ''
        self.count = 0
        self.last_scan = ''
        self.running = True
        self.paused = False
        self.icon = None
        self.last_key_time = 0
        self.max_delay = 0.05
        self.scanned_codes = set()
        self.load_data()

    def get_save_file(self):
        return SAVE_FILE_TEMPLATE.format(self.account)

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

    def load_data(self):
        save_file = self.get_save_file()
        debug_print(f"Ma'lumotlar yuklanmoqda: {save_file}")
        if os.path.exists(save_file):
            try:
                with open(save_file, newline='', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    codes = set()
                    for row in reader:
                        if row:
                            codes.add(row[0])
                    self.scanned_codes = codes
                    self.count = len(codes)
                    self.last_scan = max(codes) if codes else ''
                debug_print(f"{self.count} ta kod yuklandi. Oxirgisi: {self.last_scan}")
            except Exception as e:
                error_print(f"CSV o'qishda muammo: {e}")
        else:
            debug_print("CSV topilmadi. Yangi fayl boshlanmoqda.")
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
                        else:
                            debug_print(f"Bu kod avval kiritilgan: {self.buffer}")
                    else:
                        debug_print(f"Noto‘g‘ri kod uzunligi yoki format: {self.buffer}")
                    self.buffer = ''
            except Exception as e:
                error_print(f"Klavishani qayta ishlashda xatolik: {e}")

        debug_print("Klaviatura tinglanmoqda...")
        listener = pyn_keyboard.Listener(on_press=on_press)
        listener.start()

    def stop(self):
        debug_print("Dastur to‘xtatilmoqda...")
        self.running = False

    def update_tooltip(self):
        if self.icon:
            tooltip = f"Skannerlar soni: {self.count} | Oxirgisi: {self.last_scan or '-'} | Account: {self.account}"
            self.icon.title = tooltip

    def toggle_pause(self):
        self.paused = not self.paused
        debug_print(f"Pauza holati o‘zgardi. Hozirgi holat: {'Pauza' if self.paused else 'Faol'}")
        if self.icon:
            self.icon.icon = create_image(self.paused)

    def switch_account(self, icon, item=None, account_name=None):
        if account_name is None:
            return
        debug_print(f"Akkaunt almashtirildi: {account_name}")
        self.account = account_name
        self.save_last_account()
        self.load_data()
        self.update_tooltip()
        if self.icon:
            self.icon.icon = create_image(self.paused)

    def reset_counter(self, icon, item):
        debug_print("Skanner hisoblagichi nolga tushirilmoqda...")
        self.scanned_codes = set()
        self.count = 0
        self.last_scan = ''
        self.save_data()
        self.update_tooltip()
        if self.icon:
            self.icon.icon = create_image(self.paused)

def create_image(paused):
    color = (128, 128, 0) if paused else (0, 128, 0)
    image = Image.new('RGB', (64, 64), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, 48, 48), fill='white')
    return image

def show_message(title, msg, icon=None):
    ctypes.windll.user32.MessageBoxW(0, msg, title, 0)

def show_money(icon, item, scanner):
    total = scanner.count * 90
    debug_print(f"Pul hisoblandi: {total} so'm")
    # show_message("Man nech pul topdim?", f"Hozirgi pulingiz: {total}")

def create_menu(scanner: ScannerApp):
    account_items = [
        pystray.MenuItem(
            account,
            partial(scanner.switch_account, account_name=account),
            checked=lambda item, acc=account: scanner.account == acc,
            radio=True
        )
        for account in ACCOUNTS
    ]
    return pystray.Menu(
        pystray.MenuItem('Akkaunt', pystray.Menu(*account_items)),
        pystray.MenuItem("Hisoblagichni reset qilish", lambda icon, item: scanner.reset_counter(icon, item)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Davom ettirish" if scanner.paused else "Pauza",
            lambda icon, item: scanner.toggle_pause()
        ),
        pystray.MenuItem(
            "Man nech pul topdim?",
            lambda icon, item: show_money(icon, item, scanner)
        ),
        pystray.MenuItem(
            "Chiqish",
            lambda icon, item: (scanner.stop(), scanner.icon.stop() if scanner.icon else None)
        )
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
    return icon

if __name__ == "__main__":
    debug_print("ScannerApp ishga tushdi...")
    scanner = ScannerApp()
    scanner.start_listening()

    debug_print("System tray ikonkasi yaratilmoqda...")
    icon = create_icon(scanner)
    icon.run()
