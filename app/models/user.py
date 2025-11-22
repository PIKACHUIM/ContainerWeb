from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import json

# 使用全局db实例
from app import db

class User(UserMixin, db.Model):
    """用户模型"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # 用户状态
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    
    # 用户资源
    coins = db.Column(db.Integer, default=100, nullable=False)  # 金币
    
    # 资源限制
    max_containers = db.Column(db.Integer, default=10, nullable=False)  # 最大容器数量
    max_ports = db.Column(db.Integer, default=20, nullable=False)  # 最大端口数量
    max_storage = db.Column(db.Integer, default=10, nullable=False)  # 最大存储空间(GB)
    max_cpu = db.Column(db.Float, default=2.0, nullable=False)  # 最大CPU核心数
    max_memory = db.Column(db.Integer, default=4096, nullable=False)  # 最大内存(MB)
    
    # 权限设置 (JSON格式存储)
    host_privileges = db.Column(db.Text, default='{}')  # 主机权限
    device_access = db.Column(db.Text, default='[]')  # 设备访问权限
    gpu_access = db.Column(db.Text, default='[]')  # GPU访问权限
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime)
    
    # 关系
    containers = db.relationship('Container', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    networks = db.relationship('Network', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if not self.host_privileges:
            self.host_privileges = '{}'
        if not self.device_access:
            self.device_access = '[]'
        if not self.gpu_access:
            self.gpu_access = '[]'
    
    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """检查密码"""
        return check_password_hash(self.password_hash, password)
    
    def get_host_privileges(self):
        """获取主机权限"""
        try:
            return json.loads(self.host_privileges)
        except:
            return {}
    
    def set_host_privileges(self, privileges):
        """设置主机权限"""
        self.host_privileges = json.dumps(privileges)
    
    def get_device_access(self):
        """获取设备访问权限"""
        try:
            return json.loads(self.device_access)
        except:
            return []
    
    def set_device_access(self, devices):
        """设置设备访问权限"""
        self.device_access = json.dumps(devices)
    
    def get_gpu_access(self):
        """获取GPU访问权限"""
        try:
            return json.loads(self.gpu_access)
        except:
            return []
    
    def set_gpu_access(self, gpus):
        """设置GPU访问权限"""
        self.gpu_access = json.dumps(gpus)
    
    def get_container_count(self):
        """获取用户容器数量"""
        return self.containers.count()
    
    def get_used_ports(self):
        """获取用户已使用的端口数量"""
        used_ports = 0
        for container in self.containers:
            port_mappings = container.get_port_mappings()
            used_ports += len(port_mappings)
        return used_ports
    
    def get_used_storage(self):
        """获取用户已使用的存储空间(GB)"""
        # 这里需要实际计算容器使用的存储空间
        # 暂时返回0，实际实现时需要查询容器存储使用情况
        return 0
    
    def can_create_container(self):
        """检查是否可以创建新容器"""
        return self.get_container_count() < self.max_containers
    
    def can_use_ports(self, port_count):
        """检查是否可以使用指定数量的端口"""
        return self.get_used_ports() + port_count <= self.max_ports
    
    def can_use_storage(self, storage_gb):
        """检查是否可以使用指定存储空间"""
        return self.get_used_storage() + storage_gb <= self.max_storage
    
    def deduct_coins(self, amount):
        """扣除金币"""
        if self.coins >= amount:
            self.coins -= amount
            return True
        return False
    
    def add_coins(self, amount):
        """增加金币"""
        self.coins += amount
    
    def update_last_login(self):
        """更新最后登录时间"""
        self.last_login = datetime.utcnow()
    
    def to_dict(self, include_sensitive=False):
        """转换为字典"""
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'coins': self.coins,
            'max_containers': self.max_containers,
            'max_ports': self.max_ports,
            'max_storage': self.max_storage,
            'max_cpu': self.max_cpu,
            'max_memory': self.max_memory,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'container_count': self.get_container_count(),
            'used_ports': self.get_used_ports(),
            'used_storage': self.get_used_storage()
        }
        
        if include_sensitive:
            data.update({
                'host_privileges': self.get_host_privileges(),
                'device_access': self.get_device_access(),
                'gpu_access': self.get_gpu_access()
            })
        
        return data
    
    def __repr__(self):
        return f'<User {self.username}>'