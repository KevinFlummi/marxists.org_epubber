from flask import Flask, request, render_template, send_file, Response
import time
import sys
import os
from pathlib import Path
from io import StringIO
from threading import Thread
from queue import Queue

from processer import from_url  # Import your existing function

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import redis

script_path = Path(__file__).parent.resolve()
root_path = script_path.parent.resolve()
app = Flask(__name__, template_folder=os.path.join(root_path, 'webinterface'), static_folder=os.path.join(root_path, 'webinterface'))
redis_client = redis.Redis(host='localhost', port=6379, db=0)
limiter = Limiter(app=app, key_func=get_remote_address, storage_uri="redis://localhost:6379",default_limits=["200 per day", "50 per hour"])

# Queue to hold our output
output_queue = Queue()

# Custom stdout class to capture prints
class OutputCapturer:
    def __init__(self, queue):
        self.queue = queue

    def write(self, text):
        self.queue.put(text+"<br>")

    def flush(self):
        pass

@app.route('/', methods=['GET', 'POST'])
@limiter.limit("10 per minute")  # Specific limit for index page
def index():
    if request.method == 'POST':
        url = request.form['url']

        # Redirect to processing page
        return render_template('processing.html', url=url)

    return render_template('index.html')

@app.route('/process/<path:url>')
@limiter.limit("5 per minute")
def process(url):
    def generate():
        # Redirect stdout to our capturer
        sys.stdout = OutputCapturer(output_queue)

        # Run processing in a thread
        def process_task():
            try:
                file_path = from_url(url)
                output_queue.put(f"FILE_READY:{file_path}")
            except Exception as e:
                output_queue.put(f"ERROR:{str(e)}")

        Thread(target=process_task).start()

        # Stream output to client
        while True:
            output = output_queue.get()
            if output.startswith("FILE_READY:"):
                file_path = output.split(":")[1]
                yield f"data: {output}\n\n"
                break
            elif output.startswith("ERROR:"):
                yield f"data: {output}\n\n"
                break
            else:
                yield f"data: {output}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/download/<path:file_path>')
@limiter.limit("20 per hour")
def download(file_path):
    return send_file(
        os.path.join("..", file_path),
        as_attachment=True,
        download_name=os.path.basename(file_path)
    )

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

if __name__ == '__main__':
    app.run()
