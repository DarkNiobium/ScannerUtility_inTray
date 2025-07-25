import speech_recognition as sr
from pynput.keyboard import Controller, Key

keyboard = Controller()

COMMANDS = {
    "tasdiqla": "0001",
    "qaytar": "0003",
    "bekor": "0002",
}

def send_code(code):
    keyboard.type(code)
    keyboard.press(Key.enter)
    keyboard.release(Key.enter)
    print(f"✅ Komanda yuborildi: {code}")

def recognize_voice():
    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    print("🎤 Tinglanyapti... (Ctrl+C to exit)")
    with mic as source:
        recognizer.adjust_for_ambient_noise(source)

    while True:
        try:
            with mic as source:
                audio = recognizer.listen(source, timeout=5)
            text = recognizer.recognize_google(audio, language="uz-UZ").lower()
            print(f"🔊 Taniqlangan: {text}")
            for word, code in COMMANDS.items():
                if word in text:
                    send_code(code)
                    break
            else:
                print("🚫 Hech qanday komanda topilmadi")
        except sr.WaitTimeoutError:
            print("⌛ Hech narsa aytilmadi...")
        except sr.UnknownValueError:
            print("🤷 Ovoz tushunilmadi")
        except sr.RequestError as e:
            print(f"🌐 API xato: {e}")
        except KeyboardInterrupt:
            print("\n⛔ Chiqildi")
            break

if __name__ == "__main__":
    recognize_voice()
