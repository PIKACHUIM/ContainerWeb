import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_cors import CORS
from config import config

# 初始化扩展
db = SQLAlchemy()
login_manager = LoginManager()
socketio = SocketIO()

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '请先登录访问此页面。'
    socketio.init_app(app, cors_allowed_origins="*", async_mode='threading')
    CORS(app)
    
    # 注册蓝图
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.api import api_bp
    from app.routes.admin import admin_bp
    from app.routes.websocket import websocket_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(websocket_bp, url_prefix='/ws')
    
    # 创建数据库表
    with app.app_context():
        # 导入所有模型以确保表被创建
        from app.models.user import User
        from app.models.container import Container
        from app.models.network import Network
        from app.models.template import Template
        from app.models.system_settings import SystemSettings
        from app.models.engine import Engine
        
        db.create_all()
        
        # 创建默认管理员用户
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@containerweb.local',
                is_admin=True,
                is_active=True,
                coins=999999,
                max_containers=999,
                max_ports=999,
                max_storage=999999,
                max_cpu=999.0,
                max_memory=999999
            )
            admin.set_password('admin123')
            db.session.add(admin)
        
        # 创建系统设置
        settings = SystemSettings.query.first()
        if not settings:
            settings = SystemSettings()
            db.session.add(settings)
        
        db.session.commit()
    
    return app