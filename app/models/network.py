from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import json

# 使用全局db实例
from app import db

class Network(db.Model):
    """网络模型"""
    __tablename__ = 'networks'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # 网络基本信息
    network_id = db.Column(db.String(255), nullable=False, index=True)  # 引擎中的网络ID
    name = db.Column(db.String(255), nullable=False, index=True)  # 网络名称
    engine_name = db.Column(db.String(50), nullable=False)  # 使用的引擎名称
    
    # 网络配置
    driver = db.Column(db.String(50), default='bridge')  # 网络驱动
    subnet = db.Column(db.String(50))  # 子网
    gateway = db.Column(db.String(45))  # 网关
    
    # 网络选项 (JSON格式存储)
    options = db.Column(db.Text, default='{}')  # 网络选项
    labels = db.Column(db.Text, default='{}')  # 网络标签
    
    # 网络状态
    is_active = db.Column(db.Boolean, default=True)  # 是否激活
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # 外键关系
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    def __init__(self, **kwargs):
        super(Network, self).__init__(**kwargs)
        if not self.options:
            self.options = '{}'
        if not self.labels:
            self.labels = '{}'
    
    def get_options(self):
        """获取网络选项"""
        try:
            return json.loads(self.options)
        except:
            return {}
    
    def set_options(self, options):
        """设置网络选项"""
        self.options = json.dumps(options)
    
    def get_labels(self):
        """获取网络标签"""
        try:
            return json.loads(self.labels)
        except:
            return {}
    
    def set_labels(self, labels):
        """设置网络标签"""
        self.labels = json.dumps(labels)
    
    def get_container_count(self):
        """获取连接到此网络的容器数量"""
        return len(self.containers)
    
    def get_full_name(self):
        """获取完整网络名称（包含用户ID前缀）"""
        return f"{self.user_id}_{self.name}"
    
    def is_system_network(self):
        """检查是否为系统网络"""
        system_networks = ['bridge', 'host', 'none', 'default']
        return self.name in system_networks
    
    def can_delete(self):
        """检查是否可以删除"""
        return not self.is_system_network() and self.get_container_count() == 0
    
    def to_dict(self, include_containers=False):
        """转换为字典"""
        data = {
            'id': self.id,
            'network_id': self.network_id,
            'name': self.name,
            'full_name': self.get_full_name(),
            'engine_name': self.engine_name,
            'driver': self.driver,
            'subnet': self.subnet,
            'gateway': self.gateway,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'user_id': self.user_id,
            'container_count': self.get_container_count(),
            'options': self.get_options(),
            'labels': self.get_labels(),
            'is_system_network': self.is_system_network(),
            'can_delete': self.can_delete()
        }
        
        if include_containers:
            data['containers'] = [container.to_dict(include_config=False) for container in self.containers]
        
        return data
    
    @staticmethod
    def get_by_network_id(network_id):
        """根据网络ID获取网络"""
        return Network.query.filter_by(network_id=network_id).first()
    
    @staticmethod
    def get_by_name(name, user_id=None):
        """根据名称获取网络"""
        query = Network.query.filter_by(name=name)
        if user_id:
            query = query.filter_by(user_id=user_id)
        return query.first()
    
    @staticmethod
    def get_user_networks(user_id):
        """获取用户的网络"""
        return Network.query.filter_by(user_id=user_id).all()
    
    @staticmethod
    def get_active_networks():
        """获取所有激活的网络"""
        return Network.query.filter_by(is_active=True).all()
    
    @staticmethod
    def count_user_networks(user_id):
        """统计用户网络数量"""
        return Network.query.filter_by(user_id=user_id).count()
    
    @staticmethod
    def generate_network_name(user_id, base_name):
        """生成网络名称（用户ID_网络名称）"""
        return f"{user_id}_{base_name}"
    
    @staticmethod
    def is_name_available(name, user_id):
        """检查网络名称是否可用"""
        return Network.get_by_name(name, user_id) is None
    
    def __repr__(self):
        return f'<Network {self.name}>'