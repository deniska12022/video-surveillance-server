from flask import Flask, request, render_template_string
from flask_socketio import SocketIO
import time
import os
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'video_server_secret_123'

# Инициализируем SocketIO
try:
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
    logger.info("✅ SocketIO initialized with threading mode")
except Exception as e:
    logger.error(f"❌ SocketIO init error: {e}")
    socketio = SocketIO(app, cors_allowed_origins="*")
    logger.info("✅ SocketIO initialized with default mode")

# Хранилище клиентов
clients = {
    'cameras': {},
    'controllers': {}
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Video Server</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            min-height: 100vh;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: rgba(255,255,255,0.1);
            padding: 30px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }
        .status {
            background: rgba(255,255,255,0.2);
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }
        .stat {
            font-size: 20px;
            margin: 10px 0;
        }
        .success { color: #00ff00; }
        .info { color: #87ceeb; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎥 Video Streaming Server</h1>
        <div class="status">
            <h2 class="success">🟢 SERVER IS RUNNING</h2>
            <div class="stat">📹 Cameras: <strong>{{ cameras }}</strong></div>
            <div class="stat">🎮 Controllers: <strong>{{ controllers }}</strong></div>
            <div class="stat">⏰ Uptime: <strong>{{ uptime }}</strong></div>
            <div class="stat">🚀 Mode: <strong>{{ mode }}</strong></div>
        </div>
        <p class="info">Ready to receive video connections from clients.</p>
    </div>
</body>
</html>
"""

start_time = time.time()

def get_uptime():
    uptime = int(time.time() - start_time)
    hours = uptime // 3600
    minutes = (uptime % 3600) // 60
    seconds = uptime % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE,
                                cameras=len(clients['cameras']),
                                controllers=len(clients['controllers']),
                                uptime=get_uptime(),
                                mode=socketio.async_mode)

@app.route('/health')
def health():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "clients": {
            "cameras": len(clients['cameras']),
            "controllers": len(clients['controllers'])
        }
    }

@app.route('/test')
def test():
    return {"message": "Server is working!", "version": "1.0"}

# WebSocket handlers
@socketio.on('connect')
def handle_connect():
    logger.info(f"🔗 Client connected: {request.sid}")
    
@socketio.on('disconnect')
def handle_disconnect():
    client_id = request.sid
    # Удаляем из всех списков
    clients['cameras'].pop(client_id, None)
    clients['controllers'].pop(client_id, None)
    logger.info(f"🔌 Client disconnected: {client_id}")

@socketio.on('register_camera')
def handle_camera_register(data):
    client_id = request.sid
    camera_name = data.get('name', f'Camera_{client_id[-6:]}')
    
    clients['cameras'][client_id] = {
        'name': camera_name,
        'registered_at': time.time()
    }
    
    logger.info(f"📹 Camera registered: {camera_name}")
    
    # Уведомляем контроллеры
    socketio.emit('camera_connected', {
        'camera_id': client_id,
        'name': camera_name,
        'timestamp': time.time()
    }, room=list(clients['controllers'].keys()))

@socketio.on('register_controller')
def handle_controller_register(data):
    client_id = request.sid
    controller_name = data.get('name', 'Controller')
    
    clients['controllers'][client_id] = {
        'name': controller_name,
        'registered_at': time.time()
    }
    
    logger.info(f"🎮 Controller registered: {controller_name}")
    
    # Отправляем список камер
    available_cameras = []
    for cam_id, cam_info in clients['cameras'].items():
        available_cameras.append({
            'camera_id': cam_id,
            'name': cam_info['name']
        })
    
    socketio.emit('available_cameras', {
        'cameras': available_cameras,
        'count': len(available_cameras)
    }, room=client_id)

@socketio.on('video_frame')
def handle_video_frame(data):
    """Обработка видео кадров"""
    client_id = request.sid
    
    if client_id in clients['cameras']:
        try:
            # Пересылаем кадр всем контроллерам
            frame_data = {
                'camera_id': client_id,
                'camera_name': clients['cameras'][client_id]['name'],
                'frame': data.get('frame', ''),
                'timestamp': time.time()
            }
            
            socketio.emit('video_stream', frame_data, 
                         room=list(clients['controllers'].keys()))
                         
        except Exception as e:
            logger.error(f"❌ Video frame error: {e}")

@socketio.on('ping')
def handle_ping():
    socketio.emit('pong', {'server_time': time.time()}, room=request.sid)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    
    print("=" * 60)
    print("🚀 VIDEO STREAMING SERVER")
    print("=" * 60)
    print(f"📍 Port: {port}")
    print(f"🐍 Python: {os.environ.get('PYTHON_VERSION', 'Unknown')}")
    print(f"🔧 Async mode: {socketio.async_mode}")
    print(f"⏰ Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("📡 Waiting for client connections...")
    print("=" * 60)
    
    try:
        # 🔥 ДОБАВЛЯЕМ allow_unsafe_werkzeug=True
        socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
    except Exception as e:
        logger.error(f"💥 Server crash: {e}")
        raise
