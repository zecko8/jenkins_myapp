import os
from flask import Flask, jsonify
 
app = Flask(__name__)
 
APP_VERSION = os.environ.get('APP_VERSION', '1.0.0')
APP_ENV     = os.environ.get('APP_ENV', 'unknown')
 
@app.route('/')
def index():
    return f'''
    <html><body style="font-family:sans-serif;text-align:center;padding:50px">
    <h1>MyApp - Ambiente: {APP_ENV}</h1>
    <h2>Versione: {APP_VERSION}</h2>
    <p>Pod: {os.environ.get('HOSTNAME','unknown')}</p>
    </body></html>
    '''
 
@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'version': APP_VERSION}), 200
 
@app.route('/ready')
def ready():
    return jsonify({'ready': True}), 200
 
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
