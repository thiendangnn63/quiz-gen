import os
import json
import sqlite3
import time
import uuid
import random
import queue
import webbrowser
from threading import Timer
from functools import wraps
from flask import Flask, request, jsonify, render_template_string, Response

app = Flask(__name__)
DB_PATH = ""
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password"

active_sessions = {}
clients = []

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
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

@app.route('/quiz')
def serve_quiz():
    with open('quiz_template.html', 'r', encoding='utf-8') as f:
        return render_template_string(f.read())

@app.route('/edit/<quiz_id>')
def edit_quiz(quiz_id):
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <title>Edit Quiz</title>
    <style>
      :root { --bg: #14161a; --panel: #1c1f26; --border: #2a2e37; --text: #e7e9ec; --muted: #8a8f99; --accent: #5b8def; --accent-hover: #4a79d6; --radius: 6px; }
      * { box-sizing: border-box; }
      body { margin: 0; background: var(--bg); color: var(--text); font-family: sans-serif; line-height: 1.5; padding: 48px 20px; }
      .wrap { max-width: 640px; margin: 0 auto; }
      .question { background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; margin-bottom: 16px; }
      input, textarea { width: 100%; padding: 10px; background: var(--bg); border: 1px solid var(--border); color: var(--text); border-radius: var(--radius); margin-bottom: 8px; font-family: inherit; }
      textarea { resize: vertical; min-height: 80px; }
      button { width: 100%; padding: 14px; background: var(--accent); color: #fff; border: none; border-radius: var(--radius); font-weight: bold; cursor: pointer; margin-top: 16px; }
      button:hover { background: var(--accent-hover); }
      label { font-size: 13px; color: var(--muted); display: block; margin-bottom: 4px; margin-top: 8px; }
      .radio-group { display: flex; gap: 10px; align-items: center; margin-bottom: 8px;}
      .radio-group input[type="radio"] { width: auto; margin: 0; cursor: pointer; }
    </style>
    </head>
    <body>
    <div class="wrap">
      <h2>Edit Quiz</h2>
      <div id="editor"></div>
      <button onclick="saveQuiz()">Save & Launch Quiz</button>
    </div>
    <script>
      const quizId = window.location.pathname.split('/').pop();
      let quizData = null;

      async function load() {
        const res = await fetch(`/api/quiz/${quizId}/raw`);
        quizData = await res.json();
        const container = document.getElementById('editor');
        
        quizData.questions.forEach((q, i) => {
          let html = `<div class="question" id="q-${i}">
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

        await fetch(`/api/quiz/${quizId}/update`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(quizData)
        });

        window.location.href = `/quiz/results?quiz_id=${quizId}`;
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
        return jsonify(json.loads(f.read()))

@app.route('/api/quiz/<quiz_id>/update', methods=['POST'])
def update_quiz(quiz_id):
    filepath = f"quizzes/{quiz_id}.json"
    data = request.json
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    return jsonify({"status": "success"})

@app.route('/api/quiz/<quiz_id>/start', methods=['POST'])
def start_quiz(quiz_id):
    filepath = f"quizzes/{quiz_id}.json"
    if not os.path.exists(filepath):
        return jsonify({"error": "Quiz not found"}), 404

    with open(filepath, 'r', encoding='utf-8') as f:
        quiz_data = json.loads(f.read())

    session_token = str(uuid.uuid4())
    seed = random.random()
    
    active_sessions[session_token] = {
        "quiz_id": quiz_id,
        "start_timestamp": time.time(),
        "seed": seed
    }

    client_questions = []
    for q in quiz_data["questions"]:
        options = q["options"][:]
        random.Random(seed).shuffle(options)
        client_questions.append({
            "id": q["id"],
            "text": q["question"],
            "options": options
        })

    random.Random(seed).shuffle(client_questions)

    return jsonify({
        "session_token": session_token,
        "title": f"Quiz {quiz_id}",
        "questions": client_questions
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

    filepath = f"quizzes/{quiz_id}.json"
    with open(filepath, 'r', encoding='utf-8') as f:
        quiz_data = json.loads(f.read())

    score = 0
    total = len(quiz_data["questions"])
    results_feedback = []

    for q in quiz_data["questions"]:
        q_id = q["id"]
        correct_option = q["options"][q["correct_answer_index"]]
        selected_option = None
        is_correct = False

        if q_id in answers and answers[q_id] is not None:
            client_idx = answers[q_id]
            options = q["options"][:]
            random.Random(seed).shuffle(options)
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

    passed = score >= 8

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
    query = "SELECT name, quiz_id, time_taken, score, passed, answers_submitted FROM results"
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
        name, q_id, time_taken, score, passed, answers_json = r
        try:
            total = len(json.loads(answers_json))
        except:
            total = 10
        total = max(total, 1)
        data.append({
            "name": name,
            "quiz_id": q_id,
            "time_taken": time_taken,
            "score": score,
            "total": total,
            "passed": bool(passed)
        })
    return jsonify(data)

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
    <style>
      :root {
        --bg: #14161a;
        --panel: #1c1f26;
        --border: #2a2e37;
        --text: #e7e9ec;
        --muted: #8a8f99;
        --accent: #5b8def;
        --correct: #3fae6a;
        --incorrect: #d1554a;
        --radius: 6px;
      }
      body {
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        padding: 40px 20px;
      }
      .container {
        max-width: 900px;
        margin: 0 auto;
      }
      h1 {
        font-size: 24px;
        margin-bottom: 24px;
        border-bottom: 1px solid var(--border);
        padding-bottom: 16px;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        background: var(--panel);
        border-radius: var(--radius);
        overflow: hidden;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
      }
      th, td {
        padding: 16px;
        text-align: left;
        border-bottom: 1px solid var(--border);
      }
      th {
        background: rgba(255, 255, 255, 0.05);
        font-weight: 600;
        color: var(--muted);
        text-transform: uppercase;
        font-size: 12px;
        letter-spacing: 0.5px;
      }
      tr:last-child td {
        border-bottom: none;
      }
      .badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: bold;
      }
      .badge.pass { background: rgba(63, 174, 106, 0.2); color: var(--correct); }
      .badge.fail { background: rgba(209, 85, 74, 0.2); color: var(--incorrect); }
      .progress-bar-container {
        width: 100%;
        height: 8px;
        background: var(--bg);
        border-radius: 4px;
        display: flex;
        overflow: hidden;
        margin-top: 8px;
      }
      .progress-correct {
        background: var(--correct);
        height: 100%;
      }
      .progress-incorrect {
        background: var(--incorrect);
        height: 100%;
      }
      .score-text {
        font-size: 14px;
        font-weight: 600;
      }
    </style>
    </head>
    <body>
    <div class="container">
      <h1>Admin Results Dashboard</h1>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Quiz ID</th>
            <th>Time Taken</th>
            <th>Score</th>
            <th>Status</th>
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
                  `;
                  tbody.appendChild(tr);
              });
          } catch (e) {}
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

def start(pdf_name, quiz_id):
    global DB_PATH
    os.makedirs("database", exist_ok=True)
    DB_PATH = f"database/{pdf_name}_{quiz_id}.db"
    init_db()
    Timer(1, lambda: webbrowser.open(f"http://127.0.0.1:8080/edit/{quiz_id}")).start()
    app.run(host='0.0.0.0', port=8080, threaded=True)