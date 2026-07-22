import os
import app
import generator
import qr_generator
import time

pdf_path = 'chunks\\Chapter_1.pdf'
pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]

start = time.time()
quiz_id = generator.generate_quiz(pdf_path)
print(f"Time: {(time.time() - start):.2f} seconds")
qr_generator.qrcode_gen(quiz_id)

app.start(pdf_name, quiz_id)