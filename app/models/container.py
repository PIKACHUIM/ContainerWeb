from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import json

# 使用全局db实例
from app import db

class Container(db.Model):
    """容器模型"""
    __tablename__ = 'containers'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # 容器基本信息
    container_id = db.Column(db.String(255), nullable=False, index=True)  # 引擎中的容器ID
    name = db.Column(db.String(255), nullable=False, index=True)  # 容器名称
    image = db.Column(db.String(255), nullable=False)  # 镜像名称
    engine_name = db.Column(db.String(50), nullable=False)  # 使用的引擎名称
    
    # 容器状态
    status = db.Column(db.String(50), default='created')  # 容器状态
    
    # 容器配置 (JSON格式存储)
    port_mappings = db.Column(db.Text, default='{}')  # 端口映射
    volume_mappings = db.Column(db.Text, default='{}')  # 卷挂载
    environment_vars = db.Column(db.Text, default='{}')  # 环境变量
    
    # 资源配置
    cpu_limit = db.Column(db.Float)  # CPU限制
    memory_limit = db.Column(db.String(20))  # 内存限制
    
    # 网络配置
    network_id = db.Column(db.Integer, db.ForeignKey('networks.id'))  # 关联网络
    ip_address = db.Column(db.String(45))  # IP地址
    
    # 权限和设备
    privileged = db.Column(db.Boolean, default=False)  # 特权模式
    devices = db.Column(db.Text, default='[]')  # 设备映射
    
    # 其他配置
    command = db.Column(db.Text)  # 启动命令
    working_dir = db.Column(db.String(255))  # 工作目录
    user = db.Column(db.String(100))  # 运行用户
    restart_policy = db.Column(db.String(50), default='no')  # 重启策略
    
    # 统计信息
    cpu_usage = db.Column(db.Float, default=0.0)  # CPU使用率
    memory_usage = db.Column(db.String(20), default='0MB')  # 内存使用量
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    started_at = db.Column(db.DateTime)  # 启动时间
    stopped_at = db.Column(db.DateTime)  # 停止时间
    
    # 外键关系
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('templates.id'))  # 来源模板
    
    # 关系
    network = db.relationship('Network', backref='containers')
    template = db.relationship('Template', backref='containers')
    
    def __init__(self, **kwargs):
        super(Container, self).__init__(**kwargs)
        if not self.port_mappings:
            self.port_mappings = '{}'
        if not self.volume_mappings:
            self.volume_mappings = '{}'
        if not self.environment_vars:
            self.environment_vars = '{}'
        if not self.devices:
            self.devices = '[]'
    
    def get_port_mappings(self):
        """获取端口映射"""
        try:
            return json.loads(self.port_mappings)
        except:
            return {}
    
    def set_port_mappings(self, mappings):
        """设置端口映射"""
        self.port_mappings = json.dumps(mappings)
    
    def get_volume_mappings(self):
        """获取卷挂载"""
        try:
            return json.loads(self.volume_mappings)
        except:
            return {}
    
    def set_volume_mappings(self, mappings):
        """设置卷挂载"""
        self.volume_mappings = json.dumps(mappings)
    
    def get_environment_vars(self):
        """获取环境变量"""
        try:
            return json.loads(self.environment_vars)
        except:
            return {}
    
    def set_environment_vars(self, env_vars):
        """设置环境变量"""
        self.environment_vars = json.dumps(env_vars)
    
    def get_devices(self):
        """获取设备映射"""
        try:
            return json.loads(self.devices)
        except:
            return []
    
    def set_devices(self, device_list):
        """设置设备映射"""
        self.devices = json.dumps(device_list)
    
    def update_status(self, status):
        """更新容器状态"""
        old_status = self.status
        self.status = status
        
        # 更新时间戳
        if status == 'running' and old_status != 'running':
            self.started_at = datetime.utcnow()
        elif status in ['stopped', 'exited'] and old_status == 'running':
            self.stopped_at = datetime.utcnow()
    
    def update_stats(self, cpu_usage=None, memory_usage=None):
        """更新统计信息"""
        if cpu_usage is not None:
            self.cpu_usage = cpu_usage
        if memory_usage is not None:
            self.memory_usage = memory_usage
    
    def get_uptime(self):
        """获取运行时间"""
        if self.started_at and self.status == 'running':
            return datetime.utcnow() - self.started_at
        return None
    
    def get_port_count(self):
        """获取端口数量"""
        return len(self.get_port_mappings())
    
    def is_running(self):
        """检查是否正在运行"""
        return self.status == 'running'
    
    def is_stopped(self):
        """检查是否已停止"""
        return self.status in ['stopped', 'exited']
    
    def can_start(self):
        """检查是否可以启动"""
        return self.status in ['created', 'stopped', 'exited']
    
    def can_stop(self):
        """检查是否可以停止"""
        return self.status == 'running'
    
    def to_dict(self, include_config=True):
        """转换为字典"""
        data = {
            'id': self.id,
            'container_id': self.container_id,
            'name': self.name,
            'image': self.image,
            'engine_name': self.engine_name,
            'status': self.status,
            'cpu_usage': self.cpu_usage,
            'memory_usage': self.memory_usage,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'stopped_at': self.stopped_at.isoformat() if self.stopped_at else None,
            'user_id': self.user_id,
            'template_id': self.template_id,
            'network_id': self.network_id,
            'uptime': str(self.get_uptime()) if self.get_uptime() else None,
            'port_count': self.get_port_count()
        }
        
        if include_config:
            data.update({
                'port_mappings': self.get_port_mappings(),
                'volume_mappings': self.get_volume_mappings(),
                'environment_vars': self.get_environment_vars(),
                'devices': self.get_devices(),
                'cpu_limit': self.cpu_limit,
                'memory_limit': self.memory_limit,
                'privileged': self.privileged,
                'command': self.command,
                'working_dir': self.working_dir,
                'user': self.user,
                'restart_policy': self.restart_policy
            })
        
        return data
    
    @staticmethod
    def get_by_container_id(container_id):
        """根据容器ID获取容器"""
        return Container.query.filter_by(container_id=container_id).first()
    
    @staticmethod
    def get_by_name(name):
        """根据名称获取容器"""
        return Container.query.filter_by(name=name).first()
    
    @staticmethod
    def get_user_containers(user_id, status=None):
        """获取用户的容器"""
        query = Container.query.filter_by(user_id=user_id)
        if status:
            query = query.filter_by(status=status)
        return query.all()
    
    @staticmethod
    def get_running_containers():
        """获取所有运行中的容器"""
        return Container.query.filter_by(status='running').all()
    
    @staticmethod
    def count_user_containers(user_id):
        """统计用户容器数量"""
        return Container.query.filter_by(user_id=user_id).count()
    
    @staticmethod
    def count_containers_by_status(status):
        """按状态统计容器数量"""
        return Container.query.filter_by(status=status).count()
    
    def __repr__(self):
        return f'<Container {self.name}>'