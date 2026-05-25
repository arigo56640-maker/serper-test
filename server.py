import sys
import os
import re
import json
import queue
import threading
import subprocess

from flask import Flask, render_template, request, Response, stream_with_context

app = Flask(__name__)

_output_queue = queue.Queue()
_running = False
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def strip_ansi(text):
    return ANSI_ESCAPE.sub('', text)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/run', methods=['POST'])
def run():
    global _running
    if _running:
        return {'error': 'כבר רץ חיפוש'}, 400

    data = request.get_json() or {}
    topic = data.get('topic', 'חדשות טכנולוגיה').strip()

    while not _output_queue.empty():
        try:
            _output_queue.get_nowait()
        except queue.Empty:
            break

    _running = True

    def run_script():
        global _running
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        env['PYTHONIOENCODING'] = 'utf-8'

        try:
            process = subprocess.Popen(
                [sys.executable, '-u', 'start.py', topic],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )

            for line in iter(process.stdout.readline, ''):
                clean = strip_ansi(line)
                if clean.strip():
                    _output_queue.put(clean.rstrip('\n'))

            process.wait()
        except Exception as e:
            _output_queue.put(f"שגיאה: {e}")
        finally:
            _output_queue.put(None)
            _running = False

    threading.Thread(target=run_script, daemon=True).start()
    return {'status': 'started'}


@app.route('/stream')
def stream():
    def generate():
        while True:
            try:
                item = _output_queue.get(timeout=60)
                if item is None:
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    break
                yield f"data: {json.dumps({'line': item})}\n\n"
            except queue.Empty:
                yield f"data: {json.dumps({'ping': True})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )


@app.route('/clear-history', methods=['DELETE'])
def clear_history():
    history_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'search_history.json')
    if os.path.exists(history_file):
        os.remove(history_file)
        return {'status': 'deleted'}
    return {'status': 'not_found'}


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"פותח את הטרמינל בדפדפן על http://localhost:{port}")
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
