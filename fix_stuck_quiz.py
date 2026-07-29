#!/usr/bin/env python3
"""
Fixes a quiz stuck at status='generating' after the DB failed to update
following a successful generation run.

Checks, in order, aborting on any failure rather than guessing:
  1. quizzes/{quiz_id}.json exists and has a non-empty 'questions' list
  2. qr/qr_{quiz_id}.png exists (warning only, does not block the fix)
  3. The quiz row exists in the DB and is currently not 'ready'
Only if all of the above pass does it update status to 'ready'.

Usage:
    python fix_stuck_quiz.py <quiz_id>
    python fix_stuck_quiz.py <quiz_id> --db central_quiz.db --quizzes-dir quizzes --qr-dir qr
"""

import argparse
import json
import os
import sqlite3
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("quiz_id", help="The quiz_id to fix, e.g. fb2b64330b64d99f")
    parser.add_argument("--db", default="central_quiz.db", help="Path to the SQLite DB (default: central_quiz.db)")
    parser.add_argument("--quizzes-dir", default="quizzes", help="Directory containing quiz JSON files (default: quizzes)")
    parser.add_argument("--qr-dir", default="qr", help="Directory containing QR code PNGs (default: qr)")
    args = parser.parse_args()

    quiz_id = args.quiz_id
    quiz_path = os.path.join(args.quizzes_dir, f"{quiz_id}.json")
    qr_path = os.path.join(args.qr_dir, f"qr_{quiz_id}.png")

    # 1. Verify the quiz JSON actually exists and has real content.
    if not os.path.exists(quiz_path):
        print(f"ABORT: {quiz_path} does not exist. The quiz was likely never fully generated — this is not a DB-only issue.")
        sys.exit(1)

    try:
        with open(quiz_path, "r", encoding="utf-8") as f:
            quiz_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ABORT: {quiz_path} exists but is not valid JSON ({e}). Do not mark this quiz ready.")
        sys.exit(1)

    questions = quiz_data.get("questions", [])
    if not questions:
        print(f"ABORT: {quiz_path} has no questions. Do not mark this quiz ready.")
        sys.exit(1)

    print(f"OK: {quiz_path} exists with {len(questions)} questions.")

    # 2. Check the QR code (warn only — doesn't block the DB fix).
    if os.path.exists(qr_path):
        print(f"OK: {qr_path} exists.")
    else:
        print(f"WARNING: {qr_path} is missing. The launch page's QR image will 404 until this is regenerated.")

    # 3. Check the DB row and current status.
    if not os.path.exists(args.db):
        print(f"ABORT: DB file {args.db} does not exist.")
        sys.exit(1)

    conn = sqlite3.connect(args.db)
    try:
        cursor = conn.execute("SELECT status FROM quizzes WHERE quiz_id = ?", (quiz_id,))
        row = cursor.fetchone()

        if row is None:
            print(f"ABORT: No row for quiz_id '{quiz_id}' in the quizzes table. Nothing to update.")
            sys.exit(1)

        current_status = row[0]
        print(f"OK: Found DB row for '{quiz_id}', current status = '{current_status}'.")

        if current_status == "ready":
            print("Nothing to do — status is already 'ready'.")
            return

        conn.execute("UPDATE quizzes SET status = 'ready' WHERE quiz_id = ?", (quiz_id,))
        conn.commit()
        print(f"DONE: status for '{quiz_id}' updated to 'ready'.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()