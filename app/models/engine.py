from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import json

# 使用全局db实例
from app import db

class Engine(db.Model):
    """容器引擎模型"""
    __tablename__ = 'engines'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # 引擎基本信息
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)  # 引擎名称
    display_name = db.Column(db.String(255), nullable=False)  # 显示名称
    engine_type = db.Column(db.String(50), nullable=False)  # 引擎类型: docker, podman, lxc
    
    # 连接配置
    host = db.Column(db.String(255))  # 主机地址
    port = db.Column(db.Integer)  # 端口
    
    # 认证配置 (JSON格式存储)
    auth_config = db.Column(db.Text, default='{}')  # 认证配置
    
    # 引擎选项 (JSON格式存储)
    options = db.Column(db.Text, default='{}')  # 引擎选项
    
    # 引擎状态
    is_active = db.Column(db.Boolean, default=True)  # 是否激活
    is_default = db.Column(db.Boolean, default=False)  # 是否为默认引擎
    is_connected = db.Column(db.Boolean, default=False)  # 是否已连接
    
    # 统计信息
    container_count = db.Column(db.Integer, default=0)  # 容器数量
    image_count = db.Column(db.Integer, default=0)  # 镜像数量
    network_count = db.Column(db.Integer, default=0)  # 网络数量
    
    # 版本信息
    version = db.Column(db.String(100))  # 引擎版本
    api_version = db.Column(db.String(100))  # API版本
    
    # 系统信息 (JSON格式存储)
    system_info = db.Column(db.Text, default='{}')  # 系统信息
    
    # 健康检查
    last_ping_at = db.Column(db.DateTime)  # 最后ping时间
    ping_interval = db.Column(db.Integer, default=60)  # ping间隔(秒)
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __init__(self, **kwargs):
        super(Engine, self).__init__(**kwargs)
        if not self.auth_config:
            self.auth_config = '{}'
        if not self.options:
            self.options = '{}'
        if not self.system_info:
            self.system_info = '{}'
    
    def get_auth_config(self):
        """获取认证配置"""
        try:
            return json.loads(self.auth_config)
        except:
            return {}
    
    def set_auth_config(self, config):
        """设置认证配置"""
        self.auth_config = json.dumps(config)
    
    def get_options(self):
        """获取引擎选项"""
        try:
            return json.loads(self.options)
        except:
            return {}
    
    def set_options(self, options):
        """设置引擎选项"""
        self.options = json.dumps(options)
    
    def get_system_info(self):
        """获取系统信息"""
        try:
            return json.loads(self.system_info)
        except:
            return {}
    
    def set_system_info(self, info):
        """设置系统信息"""
        self.system_info = json.dumps(info)
    
    def get_connection_string(self):
        """获取连接字符串"""
        if self.host:
            if self.port:
                return f"{self.host}:{self.port}"
            return self.host
        return "local"
    
    def update_ping_status(self, is_connected):
        """更新ping状态"""
        self.is_connected = is_connected
        self.last_ping_at = datetime.utcnow()
    
    def update_stats(self, container_count=None, image_count=None, network_count=None):
        """更新统计信息"""
        if container_count is not None:
            self.container_count = container_count
        if image_count is not None:
            self.image_count = image_count
        if network_count is not None:
            self.network_count = network_count
    
    def is_docker(self):
        """检查是否为Docker引擎"""
        return self.engine_type == 'docker'
    
    def is_podman(self):
        """检查是否为Podman引擎"""
        return self.engine_type == 'podman'
    
    def is_lxc(self):
        """检查是否为LXC引擎"""
        return self.engine_type == 'lxc'
    
    def is_healthy(self):
        """检查引擎是否健康"""
        if not self.last_ping_at:
            return False
        
        # 检查最后ping时间是否超过间隔的2倍
        time_diff = datetime.utcnow() - self.last_ping_at
        return time_diff.total_seconds() <= (self.ping_interval * 2) and self.is_connected
    
    def can_delete(self):
        """检查是否可以删除"""
        return not self.is_default and self.container_count == 0
    
    def to_dict(self, include_sensitive=False):
        """转换为字典"""
        data = {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'engine_type': self.engine_type,
            'host': self.host,
            'port': self.port,
            'is_active': self.is_active,
            'is_default': self.is_default,
            'is_connected': self.is_connected,
            'container_count': self.container_count,
            'image_count': self.image_count,
            'network_count': self.network_count,
            'version': self.version,
            'api_version': self.api_version,
            'last_ping_at': self.last_ping_at.isoformat() if self.last_ping_at else None,
            'ping_interval': self.ping_interval,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'connection_string': self.get_connection_string(),
            'is_healthy': self.is_healthy(),
            'can_delete': self.can_delete(),
            'options': self.get_options(),
            'system_info': self.get_system_info()
        }
        
        if include_sensitive:
            data['auth_config'] = self.get_auth_config()
        
        return data
    
    @staticmethod
    def get_by_name(name):
        """根据名称获取引擎"""
        return Engine.query.filter_by(name=name).first()
    
    @staticmethod
    def get_default_engine():
        """获取默认引擎"""
        return Engine.query.filter_by(is_default=True).first()
    
    @staticmethod
    def get_active_engines():
        """获取激活的引擎"""
        return Engine.query.filter_by(is_active=True).all()
    
    @staticmethod
    def get_connected_engines():
        """获取已连接的引擎"""
        return Engine.query.filter_by(is_active=True, is_connected=True).all()
    
    @staticmethod
    def get_engines_by_type(engine_type):
        """根据类型获取引擎"""
        return Engine.query.filter_by(engine_type=engine_type, is_active=True).all()
    
    @staticmethod
    def set_default_engine(engine_id):
        """设置默认引擎"""
        # 清除所有默认标记
        Engine.query.update({'is_default': False})
        
        # 设置新的默认引擎
        engine = Engine.query.get(engine_id)
        if engine:
            engine.is_default = True
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def count_engines_by_type():
        """按类型统计引擎数量"""
        return db.session.query(
            Engine.engine_type,
            db.func.count(Engine.id)
        ).filter_by(is_active=True).group_by(Engine.engine_type).all()
    
    @staticmethod
    def get_engine_stats():
        """获取引擎统计信息"""
        total_engines = Engine.query.filter_by(is_active=True).count()
        connected_engines = Engine.query.filter_by(is_active=True, is_connected=True).count()
        total_containers = db.session.query(db.func.sum(Engine.container_count)).scalar() or 0
        total_images = db.session.query(db.func.sum(Engine.image_count)).scalar() or 0
        total_networks = db.session.query(db.func.sum(Engine.network_count)).scalar() or 0
        
        return {
            'total_engines': total_engines,
            'connected_engines': connected_engines,
            'total_containers': total_containers,
            'total_images': total_images,
            'total_networks': total_networks,
            'connection_rate': (connected_engines / total_engines * 100) if total_engines > 0 else 0
        }
    
    def __repr__(self):
        return f'<Engine {self.name}>'