from deepface import DeepFace
import cv2
import subprocess
import time

print("[INFO] Инициализация камеры...")
cap = cv2.VideoCapture(0)
time.sleep(2)

# Фиксируем твоё лицо
ret, frame = cap.read()
if not ret:
    print("[ERROR] Не удалось получить изображение.")
    cap.release()
    exit()

reference_face = frame.copy()
cv2.imwrite("reference.jpg", reference_face)
print("[INFO] Эталонное лицо сохранено.")

# Основной цикл
while True:
    ret, frame = cap.read()
    if not ret:
        continue

    try:
        result = DeepFace.verify(reference_face, frame, enforce_detection=False)

        # Если лицо отличается
        if result['verified'] == False:
            print("[ALERT] Постороннее лицо! Переключаю рабочий стол...")
            subprocess.call(["nircmd.exe", "sendkeypress", "ctrl+win+left"])
            time.sleep(5)

    except Exception as e:
        print("[WARN] Ошибка анализа:", e)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
