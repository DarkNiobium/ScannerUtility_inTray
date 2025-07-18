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
import tkinter as tk
from tkinter import ttk
import keyboard
import tkinter.messagebox as messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

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
        self.fake_var = None
        self.anim_var = None
        self.ascii_animation_enabled = True
        self.fake_enabled = False
        self.dark_theme = True
        self.anim_frame = 0
        self.session_start_time = time.time()
        self.session_start_count = 0

    def reset_speed_stats(self):
        self.session_start_time = time.time()
        self.session_start_count = self.count
        self.update_window()

    def update_window(self):
        if self.tk_window and self.status_label:
            self.status_label.config(text=f"📦 Skannerlar: {self.count}\n📌 Oxirgisi: {self.last_scan or '-'}\n👤 Akkaunt: {self.account}\n{'⏸️ [PAUZA]' if self.paused else '▶️ [FAOL]'}")
        if self.stat_label:
            elapsed = max((time.time() - self.session_start_time) / 3600, 0.01)
            scans_per_hour = (self.count - self.session_start_count) / elapsed
            avg_interval = (time.time() - self.session_start_time) / max((self.count - self.session_start_count), 1)
            stats_text = f"📈 Jami: {self.count}  |  💡 Soatiga: {scans_per_hour:.1f}  |  ⌛ Har {avg_interval:.1f} sekunda"
            if self.ascii_animation_enabled:
                anim = self.get_ascii_animation()
                stats_text += f"\n{anim}"
            self.stat_label.config(text=stats_text)

    def create_window(self):
        self.tk_window = tk.Tk()
        self.tk_window.title("📋 Skanner Ma'lumotlari")
        self.tk_window.geometry("420x340")
        self.tk_window.protocol("WM_DELETE_WINDOW", self.tk_window.withdraw)
        bg = "#2e2e2e" if self.dark_theme else "#f0f0f0"

        self.status_label = tk.Label(self.tk_window, text="", font=('Consolas', 14), justify="left", bg=bg, fg="#00ffcc")
        self.status_label.pack(padx=10, pady=(10, 0), anchor="w")

        self.stat_label = tk.Label(self.tk_window, text="", font=('Consolas', 13), justify="left", bg=bg, fg="#ffaa00")
        self.stat_label.pack(padx=10, pady=(10, 5), anchor="w")

        reset_btn = tk.Button(self.tk_window, text="🔄 Soniqni qayta boshlash", font=('Consolas', 11), command=self.reset_speed_stats, bg="#444", fg="#ffffff")
        reset_btn.pack(pady=5)

        pause_btn = tk.Button(self.tk_window, text="⏯️ Pauza/Continue", font=('Consolas', 12), command=self.toggle_pause, bg="#333", fg="#ffffff")
        pause_btn.pack(pady=5)

        self.fake_var = tk.BooleanVar(value=self.fake_enabled)
        toggle_fake = tk.Checkbutton(self.tk_window, text="🤖 Fake skan yoqilsinmi", variable=self.fake_var, command=self.toggle_fake, font=('Consolas', 12), bg=bg, fg="#ffffff", selectcolor=bg, activebackground=bg)
        toggle_fake.pack()

        self.anim_var = tk.BooleanVar(value=True)
        toggle_anim = tk.Checkbutton(self.tk_window, text="🌈 ASCII animatsiya", variable=self.anim_var, font=('Consolas', 11), bg=bg, fg="#ffffff", selectcolor=bg, activebackground=bg)
        toggle_anim.pack(pady=(5, 10))

        self.ascii_animation_enabled = True
        self.tk_window.configure(bg=bg)
        self.session_start_time = time.time()
        self.session_start_count = self.count
        self.anim_frame = 0

        self.update_window()
        self.tk_window.withdraw()
        self.tk_window.after(500, self.tick_animation)
        self.tk_window.mainloop()

    def tick_animation(self):
        self.ascii_animation_enabled = self.anim_var.get()
        self.anim_frame = (self.anim_frame + 1) % len(self.ascii_frames())
        self.update_window()
        if self.tk_window:
            self.tk_window.after(500, self.tick_animation)

    def ascii_frames(self):
        return [
            "[=     ]",
            "[==    ]",
            "[===   ]",
            "[ ===  ]",
            "[  === ]",
            "[   ===]",
            "[    ==]",
            "[     =]",
            "[      ]"
        ]

    def get_ascii_animation(self):
        return self.ascii_frames()[self.anim_frame]

    def toggle_pause(self):
        self.paused = not self.paused
        self.update_window()

    def toggle_fake(self):
        self.fake_enabled = self.fake_var.get()

    def load_last_account(self):
        return ACCOUNTS[0]  # временно заглушка для теста

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
            with open(save_file,  'w', newline='', encoding='utf-8') as f:
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
                            self.invalid_streak = 0
                            debug_print(f"Yangi kod: {self.buffer}. Jami: {self.count}")
                            self.save_data()
                            self.update_window()
                        else:
                            debug_print(f"Bu kod avval kiritilgan: {self.buffer}")
                    elif len(self.buffer) == 4:
                        debug_print("4-raqamli kod e'tiborga olinmaydi")
                    else:
                        self.invalid_streak += 1
                        debug_print(f"Noto‘g‘ri kod ({self.invalid_streak}/6): {self.buffer}")
                        if self.invalid_streak >= 6 and self.fake_enabled:
                            self.invalid_streak = 0
                            threading.Thread(target=self.fake_scan).start()
                    self.buffer = ''
            except Exception as e:
                error_print(f"Klavishani qayta ishlashda xatolik: {e}")

        debug_print("Klaviatura tinglanmoqda...")
        listener = pyn_keyboard.Listener(on_press=on_press)
        listener.start()

    def fake_scan(self):
        debug_print("Fake skan boshlanmoqda: 0001 → 3s → 0003")
        keyboard.write("0001")
        keyboard.press_and_release("enter")
        time.sleep(3)
        keyboard.write("0003")
        keyboard.press_and_release("enter")

    def stop(self):
        debug_print("Dastur to‘xtatilmoqda...")
        self.running = False
        if self.tk_window:
            self.tk_window.destroy()

    def update_tooltip(self):
        if self.icon:
            tooltip = f"Skannerlar soni: {self.count} | Oxirgisi: {self.last_scan or '-'} | Account: {self.account}"
            self.icon.title = tooltip

    def toggle_pause(self):
        self.paused = not self.paused
        debug_print(f"Pauza holati o‘zgardi. Hozirgi holat: {'Pauza' if self.paused else 'Faol'}")
        if self.icon:
            self.icon.icon = create_image(self.paused)
        self.update_window()

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
        self.update_window()

    def reset_counter(self, icon, item):
        debug_print("Skanner hisoblagichi nolga tushirilmoqda...")
        self.scanned_codes = set()
        self.count = 0
        self.last_scan = ''
        self.save_data()
        self.update_tooltip()
        self.update_window()
        if self.icon:
            self.icon.icon = create_image(self.paused)

    def toggle_window(self, *args):
        if self.tk_window:
            if self.tk_window.state() == 'withdrawn':
                self.tk_window.deiconify()
            else:
                self.tk_window.withdraw()

        def reset_speed_stats(self):
            self.session_start_time = time.time()
            self.session_start_count = self.count
            self.update_window()


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
            "Oynani ko'rsat/yop",
            lambda icon, item: scanner.toggle_window()
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
    icon.run()

if __name__ == "__main__":
    debug_print("ScannerApp ishga tushdi...")
    scanner = ScannerApp()
    scanner.start_listening()
    debug_print("System tray ikonkasi yaratilmoqda...")
    threading.Thread(target=create_icon, args=(scanner,), daemon=True).start()
    scanner.create_window()
