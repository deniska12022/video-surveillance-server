from flask import Flask, request, render_template_string
from flask_socketio import SocketIO
import eventlet
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
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .status { padding: 15px; background: #e8f5e8; border-radius: 5px; margin: 20px 0; }
        .connected { color: #2ecc71; font-weight: bold; }
        .info { background: #e3f2fd; padding: 15px; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎥 Video Streaming Server</h1>
        <div class="status">
            <p>Status: <span class="connected">🟢 RUNNING</span></p>
            <p>Cameras connected: <strong>{{ cameras_count }}</strong></p>
            <p>Controllers connected: <strong>{{ controllers_count }}</strong></p>
        </div>
        <div class="info">
            <h3>Server Information:</h3>
            <p><strong>URL:</strong> <code>{{ server_url }}</code></p>
            <p><strong>Port:</strong> {{ port }}</p>
            <p><strong>Start Time:</strong> {{ start_time }}</p>
        </div>
        <p><em>Server is ready for video connections. Use the client software to connect cameras.</em></p>
    </div>
</body>
</html>
"""

# Время запуска сервера
start_time = time.strftime("%Y-%m-%d %H:%M:%S")

@app.route('/')
def index():
    server_url = request.host_url
    port = os.environ.get('PORT', 10000)
    return render_template_string(HTML_TEMPLATE, 
                                cameras_count=len(cameras),
                                controllers_count=len(controllers),
                                server_url=server_url,
                                port=port,
                                start_time=start_time)

@app.route('/health')
def health():
    return "OK", 200

@socketio.on('connect')
def handle_connect():
    print(f"🔗 Client connected: {request.sid}")
    print(f"📊 Total cameras: {len(cameras)}, controllers: {len(controllers)}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"🔌 Client disconnected: {request.sid}")
    if request.sid in cameras:
        camera_name = cameras[request.sid]['name']
        del cameras[request.sid]
        print(f"📹 Camera removed: {camera_name}")
    if request.sid in controllers:
        del controllers[request.sid]
        print(f"🎮 Controller removed: {request.sid}")

@socketio.on('register_camera')
def handle_camera_register(data):
    camera_name = data.get('name', f'Camera_{request.sid[-4:]}')
    cameras[request.sid] = {
        'name': camera_name,
        'connected': True,
        'register_time': time.time()
    }
    print(f"📹 Camera registered: {camera_name} (ID: {request.sid})")
    
    # Уведомляем контроллеры
    socketio.emit('camera_connected', {
        'camera_id': request.sid,
        'name': camera_name,
        'timestamp': time.time()
    }, room=list(controllers.keys()))

@socketio.on('register_controller')
def handle_controller_register(data):
    controller_name = data.get('name', 'Controller')
    controllers[request.sid] = {
        'name': controller_name,
        'connected': True
    }
    print(f"🎮 Controller registered: {controller_name} (ID: {request.sid})")
    
    # Отправляем список доступных камер
    available_cameras = []
    for cam_id, cam_info in cameras.items():
        available_cameras.append({
            'camera_id': cam_id,
            'name': cam_info['name'],
            'connected_time': cam_info.get('register_time', 0)
        })
    
    socketio.emit('available_cameras', {
        'cameras': available_cameras,
        'timestamp': time.time()
    }, room=request.sid)

@socketio.on('video_frame')
def handle_video_frame(data):
    if request.sid not in cameras:
        return
        
    try:
        frame_data = {
            'camera_id': request.sid,
            'camera_name': cameras[request.sid]['name'],
            'frame': data['frame'],
            'timestamp': time.time()
        }
        
        # Отправляем всем контроллерам
        socketio.emit('video_stream', frame_data, room=list(controllers.keys()))
        
    except Exception as e:
        print(f"❌ Frame processing error: {e}")

@socketio.on('ping')
def handle_ping():
    socketio.emit('pong', {'timestamp': time.time()}, room=request.sid)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"🚀 Starting Video Streaming Server...")
    print(f"📍 Host: 0.0.0.0")
    print(f"🎯 Port: {port}")
    print(f"⏰ Start Time: {start_time}")
    print("📡 Waiting for connections...")
    
    try:
        socketio.run(app, host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        print(f"💥 Server crashed: {e}")
        raise
