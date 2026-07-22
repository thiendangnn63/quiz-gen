import sys
import socket
import qrcode
from PIL import Image

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def qrcode_gen(quiz_id):
    ip = get_local_ip()
    url = f"http://{ip}:8080/quiz?quiz_id={quiz_id}"
    img = qrcode.make(url)
    path = f"qr\\qr_{quiz_id}.png"
    img.save(path)
    with Image.open(path) as img:
        zoom = 2.0
        new_width = int(img.width * zoom)
        new_height = int(img.height * zoom)

        zoomed_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        zoomed_img.show()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        qrcode_gen(sys.argv[1])