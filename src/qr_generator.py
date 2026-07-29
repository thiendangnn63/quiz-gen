import socket
import os
import qrcode

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

def qrcode_gen(quiz_id, port):
    ip = get_local_ip()
    url = f"http://{ip}:{port}/quiz?quiz_id={quiz_id}"
    
    os.makedirs("qr", exist_ok=True)
    path = f"qr/qr_{quiz_id}.png"
    
    img = qrcode.make(url)
    img.save(path)
    
    return path