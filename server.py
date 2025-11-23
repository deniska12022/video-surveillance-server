from flask import Flask, request, render_template_string
from flask_socketio import SocketIO
import cv2
import numpy as np
import base64
import eventlet
import threading
import time
import os

# Настройка асинхронности
eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key_123'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Хранилище клиентов
cameras = {}
controllers = {}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Video Server</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .status { padding: 10px; background: #f0f0f0; border-radius: 5px; }
        .connected { color: green; }
        .disconnected { color: red; }
    </style>
</head>
<body>
    <h1>🎥 Video Streaming Server</h1>
    <div class="status">
        <p>Status: <span class="connected">🟢 RUNNING</span></p>
        <p>Cameras connected: <strong>{{ cameras_count }}</strong></p>
        <p>Controllers connected: <strong>{{ controllers_count }}</strong></p>
    </div>
    <p><em>Server is ready for video connections</em></p>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, 
                                cameras_count=len(cameras),
                                controllers_count=len(controllers))

@app.route('/health')
def health():
    return "OK", 200

@socketio.on('connect')
def handle_connect():
    print(f"🔗 Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"🔌 Client disconnected: {request.sid}")
    if request.sid in cameras:
        del cameras[request.sid]
    if request.sid in controllers:
        del controllers[request.sid]

@socketio.on('register_camera')
def handle_camera_register(data):
    cameras[request.sid] = {
        'name': data.get('name', f'Camera_{request.sid[-4:]}'),
        'connected': True
    }
    print(f"📹 Camera registered: {cameras[request.sid]['name']}")
    
    # Уведомляем контроллеры
    socketio.emit('camera_connected', {
        'camera_id': request.sid,
        'name': cameras[request.sid]['name']
    }, room=list(controllers.keys()))

@socketio.on('register_controller')
def handle_controller_register(data):
    controllers[request.sid] = {
        'name': data.get('name', 'Controller'),
        'connected': True
    }
    print(f"🎮 Controller registered: {request.sid}")
    
    # Отправляем список камер
    available_cameras = []
    for cam_id, cam_info in cameras.items():
        available_cameras.append({
            'camera_id': cam_id,
            'name': cam_info['name']
        })
    
    socketio.emit('available_cameras', {
        'cameras': available_cameras
    }, room=request.sid)

@socketio.on('video_frame')
def handle_video_frame(data):
    if request.sid not in cameras:
        return
        
    try:
        # Отправляем кадр всем контроллерам
        frame_data = {
            'camera_id': request.sid,
            'camera_name': cameras[request.sid]['name'],
            'frame': data['frame'],
            'timestamp': time.time()
        }
        
        socketio.emit('video_stream', frame_data, room=list(controllers.keys()))
        
    except Exception as e:
        print(f"❌ Frame error: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"🚀 Starting server on port {port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=False)