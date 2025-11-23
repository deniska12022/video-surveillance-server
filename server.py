from flask import Flask, render_template_string
from flask_socketio import SocketIO
import eventlet
import os
import time

# Асинхронность
eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_123'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Простое хранилище
connected_clients = {
    'cameras': {},
    'controllers': {}
}

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Video Server Status</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 40px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: rgba(255,255,255,0.1);
            padding: 30px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }
        .status-card {
            background: rgba(255,255,255,0.2);
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }
        .stat {
            font-size: 24px;
            font-weight: bold;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎥 Video Streaming Server</h1>
        <div class="status-card">
            <h2>🟢 SERVER IS RUNNING</h2>
            <div class="stat">📹 Cameras: {{ cameras_count }}</div>
            <div class="stat">🎮 Controllers: {{ controllers_count }}</div>
            <div class="stat">🕒 Uptime: {{ uptime }}</div>
        </div>
        <p><em>Ready to receive video connections</em></p>
    </div>
</body>
</html>
"""

# Время запуска
start_time = time.time()

def get_uptime():
    """Получить время работы сервера"""
    uptime_seconds = int(time.time() - start_time)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

@app.route('/')
def home():
    return render_template_string(HTML_PAGE,
                                cameras_count=len(connected_clients['cameras']),
                                controllers_count=len(connected_clients['controllers']),
                                uptime=get_uptime())

@app.route('/health')
def health():
    return {"status": "healthy", "timestamp": time.time()}, 200

@app.route('/test')
def test():
    return {"message": "Server is working!", "clients": connected_clients}, 200

# WebSocket события
@socketio.on('connect')
def handle_connect():
    client_id = request.sid
    print(f"✅ Client connected: {client_id}")

@socketio.on('disconnect')
def handle_disconnect():
    client_id = request.sid
    # Удаляем из всех списков
    connected_clients['cameras'].pop(client_id, None)
    connected_clients['controllers'].pop(client_id, None)
    print(f"❌ Client disconnected: {client_id}")

@socketio.on('register_camera')
def handle_camera(data):
    client_id = request.sid
    camera_name = data.get('name', f'Camera_{client_id[-6:]}')
    
    connected_clients['cameras'][client_id] = {
        'name': camera_name,
        'connected_at': time.time()
    }
    
    print(f"📹 Camera registered: {camera_name}")
    
    # Уведомляем контроллеры
    socketio.emit('camera_connected', {
        'camera_id': client_id,
        'name': camera_name
    }, room=list(connected_clients['controllers'].keys()))

@socketio.on('register_controller')
def handle_controller(data):
    client_id = request.sid
    controller_name = data.get('name', 'Controller')
    
    connected_clients['controllers'][client_id] = {
        'name': controller_name,
        'connected_at': time.time()
    }
    
    print(f"🎮 Controller registered: {controller_name}")
    
    # Отправляем список камер
    cameras_list = []
    for cam_id, cam_info in connected_clients['cameras'].items():
        cameras_list.append({
            'camera_id': cam_id,
            'name': cam_info['name']
        })
    
    socketio.emit('available_cameras', {
        'cameras': cameras_list
    }, room=client_id)

@socketio.on('video_frame')
def handle_video(data):
    """Получение видео кадра"""
    client_id = request.sid
    
    if client_id in connected_clients['cameras']:
        # Пересылаем всем контроллерам
        frame_data = {
            'camera_id': client_id,
            'camera_name': connected_clients['cameras'][client_id]['name'],
            'frame': data.get('frame', ''),
            'timestamp': time.time()
        }
        
        socketio.emit('video_stream', frame_data, 
                     room=list(connected_clients['controllers'].keys()))

@socketio.on('ping')
def handle_ping():
    socketio.emit('pong', {'time': time.time()}, room=request.sid)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print("=" * 50)
    print("🚀 VIDEO STREAMING SERVER STARTING...")
    print(f"📍 Port: {port}")
    print(f"⏰ Start Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("📡 Waiting for client connections...")
    print("=" * 50)
    
    try:
        socketio.run(app, host='0.0.0.0', port=port, debug=False, log_output=True)
    except Exception as e:
        print(f"💥 CRITICAL ERROR: {e}")
        raise
