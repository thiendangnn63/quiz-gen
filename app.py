# nohup python3 app.py > flask.log 2>&1 &
# pkill -f "python3 app.py"

import os
import json
import sqlite3
import time
import uuid
import random
import queue
import socket
import threading
import hashlib
from functools import wraps
from flask import Flask, request, jsonify, render_template_string, Response, send_from_directory
from werkzeug.utils import secure_filename
import src.generator as generator
import src.qr_generator as qr_generator

app = Flask(__name__)
DB_PATH = "tools/central_quiz.db"
ADMIN_USERNAME = "septhang"
ADMIN_PASSWORD = "autonxtquiz"
PORT = 5000

active_sessions = {}
clients = []
dashboard_clients = []

os.makedirs("uploads", exist_ok=True)
os.makedirs("quizzes", exist_ok=True)
os.makedirs("qr", exist_ok=True)

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quizzes (
                quiz_id TEXT PRIMARY KEY,
                title TEXT,
                status TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            conn.execute("ALTER TABLE quizzes ADD COLUMN is_active INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            print("Database error")

        try:
            conn.execute("ALTER TABLE quizzes ADD COLUMN time_limit_minutes INTEGER DEFAULT 15")
        except sqlite3.OperationalError:
            print("Database error")

        conn.execute("UPDATE quizzes SET is_active = 0")
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                quiz_id TEXT,
                session_token TEXT,
                start_timestamp REAL,
                end_timestamp REAL,
                time_taken REAL,
                score INTEGER,
                passed BOOLEAN,
                answers_submitted TEXT
            )
        """)

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != ADMIN_USERNAME or auth.password != ADMIN_PASSWORD:
            return ('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return f(*args, **kwargs)
    return decorated

def process_pdf(filepath, quiz_id, english_level="A2", q_cnt=20, difficulty="Medium"):
    try:
        questions = generator.generate_questions(
            filepath, 
            english_level=english_level, 
            q_cnt=q_cnt, 
            difficulty=difficulty
        )
        
        for i, q in enumerate(questions):
            q["id"] = f"q{i}"
            
        with open(f"quizzes/{quiz_id}.json", "w", encoding='utf-8') as f:
            json.dump({"quiz_id": quiz_id, "questions": questions}, f, indent=4)
            
        qr_generator.qrcode_gen(quiz_id, PORT)
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE quizzes SET status = 'ready' WHERE quiz_id = ?", (quiz_id,))
            
    except Exception as e:
        print(f"[Module: app, Function: process_pdf] Error generating quiz {quiz_id}: {e}")
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE quizzes SET status = 'failed' WHERE quiz_id = ?", (quiz_id,))
    
    finally:
        for q in dashboard_clients:
            q.put('update')

@app.route('/')
@requires_auth
def dashboard():
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
      :root {
        --bg: #14161c; --panel: #1c1f27; --panel-raised: #22262f;
        --border: #2b2f3a; --text: #eae7df; --muted: #82858f;
        --accent: #c9a24b; --accent-hover: #dab35e; --accent-dim: rgba(201,162,75,0.12);
        --correct: #5fae7a; --correct-dim: rgba(95,174,122,0.14);
        --incorrect: #d16656; --incorrect-dim: rgba(209,102,86,0.14);
        --info: #6b8fc9; --info-dim: rgba(107,143,201,0.14);
        --radius: 10px; --radius-sm: 6px;
        --font-display: 'Fraunces', Georgia, serif;
        --font-body: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        --font-mono: 'JetBrains Mono', Menlo, Consolas, monospace;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0; background: var(--bg); color: var(--text); font-family: var(--font-body);
        padding: 56px 20px; background-image:
          linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
        background-size: 32px 32px;
      }
      .container { max-width: 900px; margin: 0 auto; }
      .eyebrow { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--accent); margin: 0 0 6px; }
      h1 { font-family: var(--font-display); font-weight: 600; font-size: 32px; margin: 0 0 28px; border-bottom: 1px solid var(--border); padding-bottom: 20px; display: flex; justify-content: space-between; align-items: baseline; letter-spacing: -0.01em; }
      .upload-section { background: var(--panel); padding: 24px; border-radius: var(--radius); margin-bottom: 28px; border: 1px solid var(--border); }
      .upload-section h3 { font-family: var(--font-display); font-weight: 600; font-size: 16px; margin: 0 0 16px; color: var(--text); }
      .upload-row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
      input[type="file"] { color: var(--muted); font-size: 14px; font-family: var(--font-body); flex: 1; min-width: 200px; }
      input[type="file"]::file-selector-button { padding: 8px 14px; background: var(--panel-raised); color: var(--text); border: 1px solid var(--border); border-radius: var(--radius-sm); font-family: var(--font-body); font-weight: 500; cursor: pointer; margin-right: 10px; }
      button { padding: 10px 18px; background: var(--accent); color: #191305; border: none; border-radius: var(--radius-sm); font-weight: 600; font-family: var(--font-body); cursor: pointer; transition: background 0.15s ease; }
      button:hover { background: var(--accent-hover); }
      button:disabled { background: var(--border); color: var(--muted); cursor: not-allowed; }
      .config-toggle-btn { background: var(--panel-raised); color: var(--text); border: 1px solid var(--border); margin-top: 14px; display: inline-flex; align-items: center; gap: 6px; }
      .config-toggle-btn:hover { background: var(--border); }
      .config-panel { display: none; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border); }
      .config-panel.open { display: grid; }
      .config-group { display: flex; flex-direction: column; gap: 6px; }
      .config-group label { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
      .config-group select, .config-group input { background: var(--bg); border: 1px solid var(--border); color: var(--text); padding: 8px 12px; border-radius: var(--radius-sm); font-family: var(--font-body); font-size: 13px; }
      .config-group select:focus, .config-group input:focus { outline: none; border-color: var(--accent); }
      table { width: 100%; border-collapse: collapse; background: var(--panel); border-radius: var(--radius); overflow: hidden; border: 1px solid var(--border); }
      th, td { padding: 16px; text-align: left; border-bottom: 1px solid var(--border); }
      tr:last-child td { border-bottom: none; }
      tbody tr:hover { background: var(--panel-raised); }
      th { background: rgba(255, 255, 255, 0.03); font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); font-weight: 500; }
      .status-badge { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; padding: 4px 9px; border-radius: 3px; border: 1.5px dashed currentColor; display: inline-block; transform: rotate(-1.5deg); font-weight: 500; }
      .status-ready { background: var(--correct-dim); color: var(--correct); }
      .status-generating { background: var(--info-dim); color: var(--info); }
      .status-failed { background: var(--incorrect-dim); color: var(--incorrect); }
      .actions a { color: var(--accent); text-decoration: none; margin-right: 14px; font-weight: 600; font-size: 13px; }
      .actions a:hover { text-decoration: underline; }
      .empty-state { text-align: center; padding: 48px 20px; color: var(--muted); font-size: 14px; }
    </style>
    </head>
    <body>
    <div class="container">
      <h1><span><span class="eyebrow">Central Quiz</span><br>Quiz Management Dashboard</span></h1>
      <div class="upload-section">
        <h3>Create new quiz</h3>
        <form id="upload-form">
          <div class="upload-row">
            <input type="file" id="pdf-file" accept=".pdf" required>
            <button type="submit" id="upload-btn">Upload &amp; generate</button>
          </div>
          <div>
            <button type="button" class="config-toggle-btn" id="config-toggle">
              ⚙ Config Options
            </button>
          </div>
          <div class="config-panel" id="config-panel">
            <div class="config-group">
              <label for="english-level">English Level</label>
              <select id="english-level">
                <option value="A1">A1 (Beginner)</option>
                <option value="A2" selected>A2 (Elementary)</option>
                <option value="B1">B1 (Intermediate)</option>
                <option value="B2">B2 (Upper Intermediate)</option>
                <option value="C1">C1 (Advanced)</option>
                <option value="C2">C2 (Proficient)</option>
              </select>
            </div>
            <div class="config-group">
              <label for="q-cnt">Qs Count (20 for best quality)</label>
              <input type="number" id="q-cnt" value="20" min="5" max="50">
            </div>
            <div class="config-group">
              <label for="difficulty">Question Difficulty</label>
              <select id="difficulty">
                <option value="Easy">Easy</option>
                <option value="Medium" selected>Medium</option>
                <option value="Hard">Hard</option>
              </select>
            </div>
          </div>
        </form>
        <div id="upload-status" style="margin-top: 12px; font-size: 13px; color: var(--muted); font-family: var(--font-mono);"></div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Quiz ID</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="quiz-list">
        </tbody>
      </table>
    </div>
    <script>
      const uploadForm = document.getElementById('upload-form');
      const uploadBtn = document.getElementById('upload-btn');
      const uploadStatus = document.getElementById('upload-status');
      const quizList = document.getElementById('quiz-list');
      const configToggle = document.getElementById('config-toggle');
      const configPanel = document.getElementById('config-panel');

      configToggle.addEventListener('click', () => {
          configPanel.classList.toggle('open');
      });

      uploadForm.addEventListener('submit', async (e) => {
          e.preventDefault();
          const fileInput = document.getElementById('pdf-file');
          if (!fileInput.files[0]) return;

          uploadBtn.disabled = true;
          uploadStatus.textContent = "Uploading...";

          const formData = new FormData();
          formData.append('file', fileInput.files[0]);
          formData.append('english_level', document.getElementById('english-level').value);
          formData.append('q_cnt', document.getElementById('q-cnt').value);
          formData.append('difficulty', document.getElementById('difficulty').value);

          try {
              const res = await fetch('/api/upload', { method: 'POST', body: formData });
              const data = await res.json();
              if(data.status === 'success') {
                  uploadStatus.textContent = "Upload successful! Generating quiz...";
                  fileInput.value = '';
              } else {
                  uploadStatus.textContent = "Upload failed.";
              }
          } catch(err) {
              uploadStatus.textContent = "Error during upload.";
          }
          uploadBtn.disabled = false;
      });

      async function fetchQuizzes() {
          const res = await fetch('/api/quizzes');
          const data = await res.json();
          quizList.innerHTML = '';
          data.forEach(q => {
              let actions = '';
              if (q.status === 'ready') {
                  actions = `
                    <a href="/launch/${q.quiz_id}">Launch</a>
                    <a href="/edit/${q.quiz_id}">Edit</a>
                    <a href="/quiz/results?quiz_id=${q.quiz_id}">Results</a>
                  `;
              }
              actions += `<a href="#" onclick="deleteQuiz('${q.quiz_id}')" style="color: #d1554a;">Delete</a>`;
              const tr = document.createElement('tr');
              tr.innerHTML = `
                <td>${q.title}</td>
                <td style="font-family: monospace; color: var(--muted);">${q.quiz_id}</td>
                <td><span class="status-badge status-${q.status}">${q.status.toUpperCase()}</span></td>
                <td class="actions">${actions}</td>
              `;
              quizList.appendChild(tr);
          });
      }

      fetchQuizzes();
      
      async function deleteQuiz(quizId) {
          if (!confirm('Are you sure you want to delete this quiz and all its results? This cannot be undone.')) return;
          try {
              const response = await fetch(`/api/quizzes/${quizId}`, { method: 'DELETE' });
              if (!response.ok) {
                  alert('Failed to delete quiz.');
              }
          } catch (e) {
              console.error('Error deleting quiz:', e);
          }
      }
      
      const evtSource = new EventSource('/api/dashboard_stream');
      evtSource.onmessage = function(event) {
          if(event.data === 'update') {
              fetchQuizzes();
              if (uploadStatus.textContent.includes("Generating")) {
                  uploadStatus.textContent = "Process complete!";
                  setTimeout(() => uploadStatus.textContent = "", 3000);
              }
          }
      };
    </script>
    </body>
    </html>
    """
    return html

@app.route('/api/quiz/<quiz_id>/toggle', methods=['POST'])
@requires_auth
def toggle_quiz(quiz_id):
    data = request.json
    active_status = 1 if data.get("active") else 0

    with sqlite3.connect(DB_PATH) as conn:
        if active_status:
            try:
                time_limit = int(data.get("time_limit_minutes", 15))
            except (TypeError, ValueError):
                time_limit = 15
            time_limit = max(1, time_limit)
            conn.execute(
                "UPDATE quizzes SET is_active = ?, time_limit_minutes = ? WHERE quiz_id = ?",
                (active_status, time_limit, quiz_id)
            )
        else:
            conn.execute("UPDATE quizzes SET is_active = ? WHERE quiz_id = ?", (active_status, quiz_id))

    for q in dashboard_clients:
        q.put('update')

    return jsonify({"status": "success", "is_active": active_status})

@app.route('/api/quizzes/<quiz_id>', methods=['DELETE'])
@requires_auth
def delete_quiz(quiz_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM quizzes WHERE quiz_id = ?", (quiz_id,))
        conn.execute("DELETE FROM results WHERE quiz_id = ?", (quiz_id,))
    
    paths = [
        os.path.join("quizzes", f"{quiz_id}.json"),
        os.path.join("qr", f"qr_{quiz_id}.png"),
        os.path.join("uploads", f"{quiz_id}.pdf")
    ]
    
    for path in paths:
        if os.path.exists(path):
            os.remove(path)

    for q in dashboard_clients:
        q.put('update')
        
    return jsonify({"status": "success"})

@app.route('/api/upload', methods=['POST'])
@requires_auth
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400

    english_level = request.form.get('english_level', 'A2')
    try:
        q_cnt = int(request.form.get('q_cnt', 20))
    except ValueError:
        q_cnt = 20
    difficulty = request.form.get('difficulty', 'Medium')
        
    filename = secure_filename(file.filename)
    quiz_id = hashlib.sha256(f"{filename}_{time.time()}".encode()).hexdigest()[:16]
    filepath = os.path.join("uploads", f"{quiz_id}.pdf")
    file.save(filepath)
    
    title = os.path.splitext(filename)[0]
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO quizzes (quiz_id, title, status) VALUES (?, ?, ?)", (quiz_id, title, "generating"))
        
    for q in dashboard_clients:
        q.put('update')
        
    threading.Thread(
        target=process_pdf, 
        args=(filepath, quiz_id), 
        kwargs={'english_level': english_level, 'q_cnt': q_cnt, 'difficulty': difficulty}
    ).start()
    
    return jsonify({"status": "success", "quiz_id": quiz_id})

@app.route('/api/quizzes')
@requires_auth
def list_quizzes():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT quiz_id, title, status, is_active, created_at FROM quizzes ORDER BY created_at DESC")
        results = cursor.fetchall()
        
    data = [{"quiz_id": r[0], "title": r[1], "status": r[2], "is_active": bool(r[3]), "created_at": r[4]} for r in results]
    return jsonify(data)

@app.route('/api/dashboard_stream')
def dashboard_stream():
    def stream():
        q = queue.Queue()
        dashboard_clients.append(q)
        try:
            while True:
                yield f"data: {q.get()}\n\n"
        finally:
            dashboard_clients.remove(q)
    return Response(stream(), mimetype='text/event-stream')

@app.route('/launch/<quiz_id>')
@requires_auth
def launch_quiz(quiz_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_active, time_limit_minutes FROM quizzes WHERE quiz_id = ?", (quiz_id,))
        row = cursor.fetchone()

    is_active_initial = bool(row[0]) if row else False
    time_limit_initial = row[1] if row and row[1] else 15
    btn_text = "Close Session" if is_active_initial else "Start Session"
    btn_bg = "#d16656" if is_active_initial else "#5fae7a"
    js_is_active = "true" if is_active_initial else "false"

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Launch Quiz</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
      :root {{
        --bg: #14161c; --panel: #1c1f27; --border: #2b2f3a; --text: #eae7df;
        --muted: #82858f; --accent: #c9a24b;
        --font-display: 'Fraunces', Georgia, serif;
        --font-body: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        --font-mono: 'JetBrains Mono', Menlo, Consolas, monospace;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        background: var(--bg); color: var(--text); font-family: var(--font-body);
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        min-height: 100vh; margin: 0; text-align: center; padding: 20px;
        background-image:
          linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
        background-size: 32px 32px;
      }}
      .panel {{ background: var(--panel); border: 1px solid var(--border); padding: 44px 48px; border-radius: 12px; max-width: 380px; }}
      .eyebrow {{ font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--accent); margin: 0 0 10px; }}
      h1 {{ font-family: var(--font-display); font-weight: 600; font-size: 26px; margin: 0; letter-spacing: -0.01em; }}
      .qr-frame {{ background: #fff; padding: 16px; border-radius: 8px; display: inline-block; margin: 24px 0; }}
      img {{ display: block; max-width: 260px; width: 100%; }}
      .quiz-id {{ font-family: var(--font-mono); font-size: 12px; color: var(--muted); margin-bottom: 24px; }}
      button#toggle-btn {{ padding: 12px 24px; font-weight: 600; cursor: pointer; margin-bottom: 24px; border: none; border-radius: 6px; font-family: var(--font-body); font-size: 15px; color: #fff; background: {btn_bg}; transition: background 0.2s; }}
      a.primary {{ display: inline-block; color: #191305; background: var(--accent); text-decoration: none; font-size: 15px; font-weight: 600; padding: 12px 22px; border-radius: 6px; }}
      a.primary:hover {{ background: #dab35e; }}
      a.back {{ display: block; margin-top: 20px; font-size: 13px; color: var(--muted); text-decoration: none; }}
      a.back:hover {{ color: var(--text); }}
      .timer-box {{ text-align: center; margin-bottom: 20px; }}
      .timer-box label {{ display: block; font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; }}
      .timer-box .timer-input-row {{ display: flex; align-items: center; justify-content: center; gap: 8px; }}
      .timer-box input {{ width: 70px; padding: 8px 10px; background: var(--bg); border: 1px solid var(--border); color: var(--text); border-radius: 6px; font-family: var(--font-body); font-size: 15px; text-align: center; }}
      .timer-box input:focus {{ outline: none; border-color: var(--accent); }}
      .timer-box span {{ font-size: 13px; color: var(--muted); }}
    </style>
    </head>
    <body>
      <div class="panel">
        <p class="eyebrow">Central Quiz</p>
        <h1>Manage Session</h1>
        <div class="qr-frame">
          <img src="/qr/qr_{quiz_id}.png" alt="QR Code">
        </div>
        <div class="quiz-id">{quiz_id}</div>
        <div class="timer-box">
          <label for="time-limit-input">Timer</label>
          <div class="timer-input-row">
            <input type="number" id="time-limit-input" min="1" value="{time_limit_initial}" {"disabled" if is_active_initial else ""}>
            <span>minutes</span>
          </div>
        </div>
        <button id="toggle-btn" onclick="toggleSession()">{btn_text}</button>
        <br>
        <a class="primary" href="/quiz?quiz_id={quiz_id}" target="_blank">Open on this device</a>
        <a class="back" href="/">&larr; Back to dashboard</a>
      </div>
      <script>
        let isActive = {js_is_active};
        const quizId = "{quiz_id}";
        const btn = document.getElementById('toggle-btn');
        const timeLimitInput = document.getElementById('time-limit-input');

        async function toggleSession() {{
            isActive = !isActive;
            try {{
                await fetch(`/api/quiz/${{quizId}}/toggle`, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        active: isActive,
                        time_limit_minutes: parseInt(timeLimitInput.value, 10) || 15
                    }})
                }});
                updateUI();
            }} catch (e) {{
                isActive = !isActive;
                alert("Failed to toggle session");
            }}
        }}

        function updateUI() {{
            if (isActive) {{
                btn.textContent = "Close Session";
                btn.style.background = "#d16656";
                timeLimitInput.disabled = true;
            }} else {{
                btn.textContent = "Start Session";
                btn.style.background = "#5fae7a";
                timeLimitInput.disabled = false;
            }}
        }}
      </script>
    </body>
    </html>
    """
    return html

@app.route('/qr/<path:filename>')
def serve_qr(filename):
    return send_from_directory('qr', filename)

@app.route('/quiz')
def serve_quiz():
    with open('tools/quiz_template.html', 'r', encoding='utf-8') as f:
        return render_template_string(f.read())

@app.route('/edit/<quiz_id>')
@requires_auth
def edit_quiz(quiz_id):
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Edit Quiz</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
      :root {
        --bg: #14161c; --panel: #1c1f27; --border: #2b2f3a; --text: #eae7df;
        --muted: #82858f; --accent: #c9a24b; --accent-hover: #dab35e;
        --correct: #5fae7a; --radius: 10px; --radius-sm: 6px;
        --font-display: 'Fraunces', Georgia, serif;
        --font-body: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        --font-mono: 'JetBrains Mono', Menlo, Consolas, monospace;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0; background: var(--bg); color: var(--text); font-family: var(--font-body);
        line-height: 1.5; padding: 48px 20px;
        background-image:
          linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
        background-size: 32px 32px;
      }
      .wrap { max-width: 640px; margin: 0 auto; }
      .header-links { margin-bottom: 20px; }
      .header-links a { color: var(--muted); text-decoration: none; font-weight: 500; font-size: 13px; }
      .header-links a:hover { color: var(--text); }
      h2 { font-family: var(--font-display); font-weight: 600; font-size: 26px; margin: 0 0 24px; letter-spacing: -0.01em; }
      .question { background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); padding: 22px; margin-bottom: 16px; position: relative; }
      .question::before { content: attr(data-index); position: absolute; top: -10px; left: 18px; background: var(--accent); color: #191305; font-family: var(--font-mono); font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 3px; }
      input, textarea { width: 100%; padding: 10px 12px; background: var(--bg); border: 1px solid var(--border); color: var(--text); border-radius: var(--radius-sm); margin-bottom: 8px; font-family: var(--font-body); font-size: 14px; }
      input:focus, textarea:focus { outline: none; border-color: var(--accent); }
      textarea { resize: vertical; min-height: 72px; }
      button { width: 100%; padding: 14px; background: var(--accent); color: #191305; border: none; border-radius: var(--radius-sm); font-weight: 600; font-family: var(--font-body); font-size: 15px; cursor: pointer; margin-top: 16px; }
      button:hover { background: var(--accent-hover); }
      label { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); display: block; margin-bottom: 6px; margin-top: 12px; }
      .radio-group { display: flex; gap: 10px; align-items: center; margin-bottom: 8px;}
      .radio-group input[type="radio"] { width: auto; margin: 0; cursor: pointer; accent-color: var(--correct); }
      .radio-group input[type="text"] { margin-bottom: 0; }
      .sticky-bar {
        position: sticky; top: 0; z-index: 10;
        display: flex; align-items: center; justify-content: space-between; gap: 16px;
        background: var(--bg);
        margin: -48px -20px 24px; padding: 32px 20px 16px;
        border-bottom: 1px solid var(--border);
      }
      .sticky-bar h2 { margin: 0; }
      #save-btn { width: auto; margin: 0; padding: 10px 20px; flex-shrink: 0; }
      #save-btn:disabled { background: var(--border); color: var(--muted); cursor: not-allowed; }
    </style>
    </head>
    <body>
    <div class="wrap">
    <div class="sticky-bar">
        <div>
        <div class="header-links" style="margin-bottom: 8px;"><a href="/">&larr; Back to dashboard</a></div>
        <h2>Edit quiz</h2>
        </div>
        <button id="save-btn" onclick="saveQuiz()">Save changes</button>
    </div>
    <div id="active-warning" style="display:none; background: var(--incorrect-dim, rgba(209,102,86,0.14)); color: var(--incorrect); border: 1px solid var(--incorrect); border-radius: var(--radius-sm); padding: 12px 16px; margin-bottom: 20px; font-size: 13px;">
        This quiz session is currently active. Close it from the dashboard before editing, or in-progress attempts may be graded incorrectly.
    </div>
    <label>Title</label>
    <input type="text" id="quiz-title">
    <div id="editor"></div>
    </div>
    <script>
      const quizId = window.location.pathname.split('/').pop();
      let quizData = null;

      async function load() {
        const res = await fetch(`/api/quiz/${quizId}/raw`);
        quizData = await res.json();
        if (quizData.is_active) {
          document.getElementById('active-warning').style.display = 'block';
          document.getElementById('save-btn').disabled = true;
        }
        document.getElementById('quiz-title').value = quizData.title || '';
        const container = document.getElementById('editor');
        
        quizData.questions.forEach((q, i) => {
          let html = `<div class="question" id="q-${i}" data-index="Q${i+1}">
            <label>Question ${i+1}</label>
            <textarea class="q-text">${q.question}</textarea>
            <label>Options (Select the correct answer)</label>`;
          
          q.options.forEach((opt, j) => {
            const checked = q.correct_answer_index === j ? 'checked' : '';
            html += `<div class="radio-group">
              <input type="radio" name="correct-${i}" value="${j}" ${checked}>
              <input type="text" class="q-opt" value="${opt}">
            </div>`;
          });

          html += `<label>Explanation</label>
            <textarea class="q-exp">${q.explanation}</textarea>
          </div>`;
          container.innerHTML += html;
        });
      }

      async function saveQuiz() {
        const questions = [];
        document.querySelectorAll('.question').forEach((el, i) => {
          const qText = el.querySelector('.q-text').value;
          const options = Array.from(el.querySelectorAll('.q-opt')).map(inp => inp.value);
          const correctRadio = el.querySelector(`input[name="correct-${i}"]:checked`);
          const correctIdx = correctRadio ? parseInt(correctRadio.value) : 0;
          const explanation = el.querySelector('.q-exp').value;
          
          questions.push({
            id: quizData.questions[i].id,
            question: qText,
            options: options,
            correct_answer_index: correctIdx,
            explanation: explanation
          });
        });

        quizData.questions = questions;
        quizData.title = document.getElementById('quiz-title').value;

        const res = await fetch(`/api/quiz/${quizId}/update`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(quizData)
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          alert(err.error || 'Failed to save changes.');
          return;
        }

        window.location.href = `/`;
      }

      load();
    </script>
    </body>
    </html>
    """
    return html

@app.route('/api/quiz/<quiz_id>/raw', methods=['GET'])
def raw_quiz(quiz_id):
    filepath = f"quizzes/{quiz_id}.json"
    if not os.path.exists(filepath):
        return jsonify({"error": "Quiz not found"}), 404
    with open(filepath, 'r', encoding='utf-8') as f:
        quiz_data = json.loads(f.read())
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT title, is_active FROM quizzes WHERE quiz_id = ?", (quiz_id,)).fetchone()
    quiz_data["title"] = row[0] if row else ""
    quiz_data["is_active"] = bool(row[1]) if row else False
    return jsonify(quiz_data)

@app.route('/api/quiz/<quiz_id>/update', methods=['POST'])
@requires_auth
def update_quiz(quiz_id):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT is_active FROM quizzes WHERE quiz_id = ?", (quiz_id,)).fetchone()
    if row and row[0]:
        return jsonify({"error": "Close the session before editing this quiz."}), 409

    filepath = f"quizzes/{quiz_id}.json"
    data = request.json
    title = data.pop("title", None)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    if title is not None:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE quizzes SET title = ? WHERE quiz_id = ?", (title, quiz_id))
    return jsonify({"status": "success"})

@app.route('/api/quiz/<quiz_id>/start', methods=['POST'])
def start_quiz(quiz_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_active, time_limit_minutes FROM quizzes WHERE quiz_id = ?", (quiz_id,))
        row = cursor.fetchone()

    if not row or not row[0]:
        return jsonify({"error": "This quiz is not currently accepting responses."}), 403

    time_limit_minutes = row[1] if row[1] else 15

    filepath = f"quizzes/{quiz_id}.json"
    if not os.path.exists(filepath):
        return jsonify({"error": "Quiz not found"}), 404

    with open(filepath, 'r', encoding='utf-8') as f:
        quiz_data = json.loads(f.read())

    session_token = str(uuid.uuid4())
    seed = random.random()

    bank = quiz_data["questions"]
    sample = min(10, len(bank))
    selected_qs = random.Random(seed).sample(bank, sample)
    
    active_sessions[session_token] = {
        "quiz_id": quiz_id,
        "start_timestamp": time.time(),
        "seed": seed,
        "question_ids": [q["id"] for q in selected_qs]
    }

    client_questions = []
    for q in selected_qs:
        options = q["options"][:]
        random.Random(f"{seed}_{q['id']}").shuffle(options)
        client_questions.append({
            "id": q["id"],
            "text": q["question"],
            "options": options
        })

    random.Random(seed).shuffle(client_questions)

    return jsonify({
        "session_token": session_token,
        "title": f"Quiz {quiz_id}",
        "questions": client_questions,
        "time_limit_seconds": time_limit_minutes * 60
    })

@app.route('/api/quiz/<quiz_id>/submit', methods=['POST'])
def submit_quiz(quiz_id):
    data = request.json
    session_token = data.get("session_token")
    name = data.get("name")
    answers = data.get("answers")

    if session_token not in active_sessions or active_sessions[session_token]["quiz_id"] != quiz_id:
        return jsonify({"error": "Invalid session"}), 400

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM results WHERE name = ? AND quiz_id = ?", (name, quiz_id))
        if cursor.fetchone():
            return jsonify({"error": "Retakes are not allowed"}), 403

    session_data = active_sessions.pop(session_token)
    end_timestamp = time.time()
    start_timestamp = session_data["start_timestamp"]
    time_taken = end_timestamp - start_timestamp
    seed = session_data["seed"]
    assigned_ids = set(session_data["question_ids"])

    filepath = f"quizzes/{quiz_id}.json"
    with open(filepath, 'r', encoding='utf-8') as f:
        quiz_data = json.loads(f.read())

    score = 0
    results_feedback = []

    assigned_qs = [q for q in quiz_data["questions"] if q["id"] in assigned_ids]
    total = len(assigned_qs)

    for q in assigned_qs:
        q_id = q["id"]
        correct_option = q["options"][q["correct_answer_index"]]
        selected_option = None
        is_correct = False

        if q_id in answers and answers[q_id] is not None:
            client_idx = answers[q_id]
            options = q["options"][:]
            random.Random(f"{seed}_{q_id}").shuffle(options)
            selected_option = options[client_idx]
            
            if selected_option == correct_option:
                score += 1
                is_correct = True
        
        results_feedback.append({
            "id": q_id,
            "question": q["question"],
            "selected_option": selected_option,
            "correct_option": correct_option,
            "is_correct": is_correct,
            "explanation": q["explanation"]
        })

    passed = score >= int(total * 0.8)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO results (name, quiz_id, session_token, start_timestamp, end_timestamp, time_taken, score, passed, answers_submitted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, quiz_id, session_token, start_timestamp, end_timestamp, time_taken, score, passed, json.dumps(answers)))

    for q in clients:
        q.put('update')

    return jsonify({
        "score": score,
        "total": total,
        "passed": passed,
        "time_taken": f"{int(time_taken // 60)}m {int(time_taken % 60)}s",
        "feedback": results_feedback
    })

@app.route('/api/results_data')
@requires_auth
def results_data():
    quiz_id_filter = request.args.get('quiz_id')
    query = "SELECT id, name, quiz_id, time_taken, score, passed, answers_submitted FROM results"
    params = []
    if quiz_id_filter:
        query += " WHERE quiz_id = ?"
        params.append(quiz_id_filter)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()

    data = []
    for r in results:
        row_id, name, q_id, time_taken, score, passed, answers_json = r
        try:
            total = len(json.loads(answers_json))
        except:
            total = 10
        total = max(total, 1)
        data.append({
            "id": row_id,
            "name": name,
            "quiz_id": q_id,
            "time_taken": time_taken,
            "score": score,
            "total": total,
            "passed": bool(passed)
        })
    return jsonify(data)

@app.route('/api/results/<int:result_id>', methods=['DELETE'])
@requires_auth
def delete_result(result_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM results WHERE id = ?", (result_id,))
    
    for q in clients:
        q.put('update')
        
    return jsonify({"status": "success"})

@app.route('/api/results_stream')
def results_stream():
    def stream():
        q = queue.Queue()
        clients.append(q)
        try:
            while True:
                yield f"data: {q.get()}\n\n"
        finally:
            clients.remove(q)
    return Response(stream(), mimetype='text/event-stream')

@app.route('/quiz/results')
@requires_auth
def quiz_results():
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quiz Results</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
      :root {
        --bg: #14161c;
        --panel: #1c1f27;
        --panel-raised: #22262f;
        --border: #2b2f3a;
        --text: #eae7df;
        --muted: #82858f;
        --accent: #c9a24b;
        --correct: #5fae7a;
        --correct-dim: rgba(95,174,122,0.14);
        --incorrect: #d16656;
        --incorrect-dim: rgba(209,102,86,0.14);
        --radius: 10px;
        --font-display: 'Fraunces', Georgia, serif;
        --font-body: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        --font-mono: 'JetBrains Mono', Menlo, Consolas, monospace;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0; background: var(--bg); color: var(--text); font-family: var(--font-body); padding: 56px 20px;
        background-image:
          linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
        background-size: 32px 32px;
      }
      .container { max-width: 900px; margin: 0 auto; }
      .eyebrow { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--accent); margin: 0 0 6px; display: block; }
      h1 { font-family: var(--font-display); font-weight: 600; font-size: 32px; margin: 0 0 28px; border-bottom: 1px solid var(--border); padding-bottom: 20px; display: flex; justify-content: space-between; align-items: baseline; letter-spacing: -0.01em; }
      .header-links a { color: var(--muted); text-decoration: none; font-size: 13px; font-weight: 500; }
      .header-links a:hover { color: var(--text); }
      table { width: 100%; border-collapse: collapse; background: var(--panel); border-radius: var(--radius); overflow: hidden; border: 1px solid var(--border); }
      th, td { padding: 16px; text-align: left; border-bottom: 1px solid var(--border); }
      th { background: rgba(255, 255, 255, 0.03); font-weight: 500; color: var(--muted); text-transform: uppercase; font-size: 11px; letter-spacing: 0.1em; font-family: var(--font-mono); }
      tr:last-child td { border-bottom: none; }
      tbody tr:hover { background: var(--panel-raised); }
      .badge { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; padding: 4px 9px; border-radius: 3px; border: 1.5px dashed currentColor; display: inline-block; transform: rotate(-1.5deg); font-weight: 500; }
      .badge.pass { background: var(--correct-dim); color: var(--correct); }
      .badge.fail { background: var(--incorrect-dim); color: var(--incorrect); }
      .progress-bar-container { width: 100%; height: 6px; background: var(--bg); border-radius: 3px; display: flex; overflow: hidden; margin-top: 8px; }
      .progress-correct { background: var(--correct); height: 100%; }
      .progress-incorrect { background: var(--incorrect); height: 100%; }
      .score-text { font-size: 14px; font-weight: 600; font-family: var(--font-mono); }
      .delete-btn { background: transparent; color: var(--incorrect); border: 1px solid var(--incorrect-dim); padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: 600; font-family: var(--font-body); }
      .delete-btn:hover { background: var(--incorrect-dim); }
      .empty-state { text-align: center; padding: 48px 20px; color: var(--muted); font-size: 14px; }
    </style>
    </head>
    <body>
    <div class="container">
      <h1>
        <span><span class="eyebrow">Central Quiz</span>Results</span>
        <span class="header-links"><a href="/">&larr; Back to dashboard</a></span>
      </h1>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Quiz ID</th>
            <th>Time Taken</th>
            <th>Score</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="results-body">
        </tbody>
      </table>
    </div>
    <script>
      const urlParams = new URLSearchParams(window.location.search);
      const quizId = urlParams.get('quiz_id');
      let fetchUrl = '/api/results_data';
      if (quizId) fetchUrl += '?quiz_id=' + quizId;

      async function fetchResults() {
          try {
              const response = await fetch(fetchUrl);
              if (!response.ok) return;
              const data = await response.json();
              
              const tbody = document.getElementById('results-body');
              tbody.innerHTML = '';
              
              data.forEach(row => {
                  const correctPct = (row.score / row.total) * 100;
                  const incorrectPct = 100 - correctPct;
                  const statusClass = row.passed ? 'pass' : 'fail';
                  const statusText = row.passed ? 'Pass' : 'Fail';
                  const timeMins = Math.floor(row.time_taken / 60);
                  const timeSecs = Math.floor(row.time_taken % 60);
                  const timeStr = `${timeMins}m ${timeSecs}s`;
                  
                  const tr = document.createElement('tr');
                  tr.innerHTML = `
                    <td>${row.name}</td>
                    <td style="font-family: monospace; color: var(--muted);">${row.quiz_id}</td>
                    <td>${timeStr}</td>
                    <td>
                      <div class="score-text">${row.score} / ${row.total}</div>
                      <div class="progress-bar-container">
                        <div class="progress-correct" style="width: ${correctPct}%;"></div>
                        <div class="progress-incorrect" style="width: ${incorrectPct}%;"></div>
                      </div>
                    </td>
                    <td><span class="badge ${statusClass}">${statusText}</span></td>
                    <td><button class="delete-btn" onclick="deleteResult(${row.id})">Delete</button></td>
                  `;
                  tbody.appendChild(tr);
              });
          } catch (e) {}
      }

      async function deleteResult(id) {
          if (!confirm('Are you sure you want to delete this result?')) return;
          try {
              const response = await fetch(`/api/results/${id}`, { method: 'DELETE' });
              if (!response.ok) {
                  alert('Failed to delete result.');
              }
          } catch (e) {
              console.error(e);
          }
      }

      fetchResults();
      
      const evtSource = new EventSource('/api/results_stream');
      evtSource.onmessage = function(event) {
          if(event.data === 'update') {
              fetchResults();
          }
      };
    </script>
    </body>
    </html>
    """
    return html

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

if __name__ == "__main__":
    init_db()
    ip = get_local_ip()
    print(f"\nAdmin Dashboard: http://{ip}:{PORT}/\n")
    app.run(host='0.0.0.0', port=PORT, threaded=True)