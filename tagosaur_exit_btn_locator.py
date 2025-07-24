import pyautogui
import cv2
import numpy as np
from PIL import ImageGrab
import time

def locate_and_click_button(template_path, threshold=0.7):
    # Сделать скриншот всего экрана
    screenshot = ImageGrab.grab()
    screenshot_np = np.array(screenshot)
    screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_BGR2GRAY)

    # Загрузить шаблон кнопки
    template = cv2.imread(template_path, 0)
    w, h = template.shape[::-1]

    # Найти совпадения
    result = cv2.matchTemplate(screenshot_gray, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    print(f"Max match: {max_val:.3f}")
    if max_val >= threshold:
        x, y = max_loc
        center_x, center_y = x + w // 2, y + h // 2
        pyautogui.moveTo(center_x, center_y)
        pyautogui.click()
        return True
    else:
        return False

while True:
    time.sleep(2)  # Дай время на переключение окна
    locate_and_click_button("exit_button.png", threshold=0.75)
