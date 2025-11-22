from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import json

# 使用全局db实例
from app import db

class SystemSettings(db.Model):
    """系统设置模型"""
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # 注册设置
    allow_registration = db.Column(db.Boolean, default=True)  # 允许注册
    registration_code = db.Column(db.String(255))  # 注册码
    require_email_verification = db.Column(db.Boolean, default=False)  # 需要邮箱验证
    
    # 默认用户限制
    default_max_containers = db.Column(db.Integer, default=10)  # 默认最大容器数量
    default_max_ports = db.Column(db.Integer, default=20)  # 默认最大端口数量
    default_max_storage = db.Column(db.Integer, default=10)  # 默认最大存储空间(GB)
    default_max_cpu = db.Column(db.Float, default=2.0)  # 默认最大CPU核心数
    default_max_memory = db.Column(db.Integer, default=4096)  # 默认最大内存(MB)
    default_coins = db.Column(db.Integer, default=100)  # 默认金币数量
    
    # 系统资源限制
    system_max_containers = db.Column(db.Integer, default=1000)  # 系统最大容器数量
    system_max_cpu = db.Column(db.Float, default=100.0)  # 系统最大CPU核心数
    system_max_memory = db.Column(db.Integer, default=102400)  # 系统最大内存(MB)
    system_max_storage = db.Column(db.Integer, default=1000)  # 系统最大存储空间(GB)
    
    # 物理设备权限 (JSON格式存储)
    available_devices = db.Column(db.Text, default='[]')  # 可用设备列表
    available_gpus = db.Column(db.Text, default='[]')  # 可用GPU列表
    
    # 网络设置
    network_subnet_base = db.Column(db.String(50), default='172.20.0.0/16')  # 网络子网基础
    allow_custom_networks = db.Column(db.Boolean, default=True)  # 允许自定义网络
    
    # 安全设置
    session_timeout = db.Column(db.Integer, default=3600)  # 会话超时时间(秒)
    max_login_attempts = db.Column(db.Integer, default=5)  # 最大登录尝试次数
    lockout_duration = db.Column(db.Integer, default=300)  # 锁定持续时间(秒)
    
    # 日志设置
    log_level = db.Column(db.String(20), default='INFO')  # 日志级别
    log_retention_days = db.Column(db.Integer, default=30)  # 日志保留天数
    
    # 备份设置
    auto_backup_enabled = db.Column(db.Boolean, default=False)  # 自动备份
    backup_interval_hours = db.Column(db.Integer, default=24)  # 备份间隔(小时)
    backup_retention_days = db.Column(db.Integer, default=7)  # 备份保留天数
    
    # 监控设置
    monitoring_enabled = db.Column(db.Boolean, default=True)  # 启用监控
    stats_collection_interval = db.Column(db.Integer, default=60)  # 统计收集间隔(秒)
    
    # 通知设置
    email_notifications = db.Column(db.Boolean, default=False)  # 邮件通知
    smtp_server = db.Column(db.String(255))  # SMTP服务器
    smtp_port = db.Column(db.Integer, default=587)  # SMTP端口
    smtp_username = db.Column(db.String(255))  # SMTP用户名
    smtp_password = db.Column(db.String(255))  # SMTP密码
    smtp_use_tls = db.Column(db.Boolean, default=True)  # 使用TLS
    
    # 维护模式
    maintenance_mode = db.Column(db.Boolean, default=False)  # 维护模式
    maintenance_message = db.Column(db.Text)  # 维护消息
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __init__(self, **kwargs):
        super(SystemSettings, self).__init__(**kwargs)
        if not self.available_devices:
            self.available_devices = '[]'
        if not self.available_gpus:
            self.available_gpus = '[]'
    
    def get_available_devices(self):
        """获取可用设备列表"""
        try:
            return json.loads(self.available_devices)
        except:
            return []
    
    def set_available_devices(self, devices):
        """设置可用设备列表"""
        self.available_devices = json.dumps(devices)
    
    def get_available_gpus(self):
        """获取可用GPU列表"""
        try:
            return json.loads(self.available_gpus)
        except:
            return []
    
    def set_available_gpus(self, gpus):
        """设置可用GPU列表"""
        self.available_gpus = json.dumps(gpus)
    
    def is_registration_allowed(self):
        """检查是否允许注册"""
        return self.allow_registration and not self.maintenance_mode
    
    def verify_registration_code(self, code):
        """验证注册码"""
        if not self.registration_code:
            return True  # 没有设置注册码则允许注册
        return self.registration_code == code
    
    def is_maintenance_mode(self):
        """检查是否为维护模式"""
        return self.maintenance_mode
    
    def get_default_user_limits(self):
        """获取默认用户限制"""
        return {
            'max_containers': self.default_max_containers,
            'max_ports': self.default_max_ports,
            'max_storage': self.default_max_storage,
            'max_cpu': self.default_max_cpu,
            'max_memory': self.default_max_memory,
            'coins': self.default_coins
        }
    
    def get_system_limits(self):
        """获取系统限制"""
        return {
            'max_containers': self.system_max_containers,
            'max_cpu': self.system_max_cpu,
            'max_memory': self.system_max_memory,
            'max_storage': self.system_max_storage
        }
    
    def get_smtp_config(self):
        """获取SMTP配置"""
        return {
            'server': self.smtp_server,
            'port': self.smtp_port,
            'username': self.smtp_username,
            'password': self.smtp_password,
            'use_tls': self.smtp_use_tls
        }
    
    def to_dict(self, include_sensitive=False):
        """转换为字典"""
        data = {
            'id': self.id,
            'allow_registration': self.allow_registration,
            'require_email_verification': self.require_email_verification,
            'default_max_containers': self.default_max_containers,
            'default_max_ports': self.default_max_ports,
            'default_max_storage': self.default_max_storage,
            'default_max_cpu': self.default_max_cpu,
            'default_max_memory': self.default_max_memory,
            'default_coins': self.default_coins,
            'system_max_containers': self.system_max_containers,
            'system_max_cpu': self.system_max_cpu,
            'system_max_memory': self.system_max_memory,
            'system_max_storage': self.system_max_storage,
            'available_devices': self.get_available_devices(),
            'available_gpus': self.get_available_gpus(),
            'network_subnet_base': self.network_subnet_base,
            'allow_custom_networks': self.allow_custom_networks,
            'session_timeout': self.session_timeout,
            'max_login_attempts': self.max_login_attempts,
            'lockout_duration': self.lockout_duration,
            'log_level': self.log_level,
            'log_retention_days': self.log_retention_days,
            'auto_backup_enabled': self.auto_backup_enabled,
            'backup_interval_hours': self.backup_interval_hours,
            'backup_retention_days': self.backup_retention_days,
            'monitoring_enabled': self.monitoring_enabled,
            'stats_collection_interval': self.stats_collection_interval,
            'email_notifications': self.email_notifications,
            'smtp_server': self.smtp_server,
            'smtp_port': self.smtp_port,
            'smtp_use_tls': self.smtp_use_tls,
            'maintenance_mode': self.maintenance_mode,
            'maintenance_message': self.maintenance_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sensitive:
            data.update({
                'registration_code': self.registration_code,
                'smtp_username': self.smtp_username,
                'smtp_password': self.smtp_password
            })
        
        return data
    
    @staticmethod
    def get_settings():
        """获取系统设置（单例模式）"""
        settings = SystemSettings.query.first()
        if not settings:
            settings = SystemSettings()
            db.session.add(settings)
            db.session.commit()
        return settings
    
    @staticmethod
    def update_settings(data):
        """更新系统设置"""
        settings = SystemSettings.get_settings()
        
        # 更新字段
        for key, value in data.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        return settings
    
    def __repr__(self):
        return f'<SystemSettings {self.id}>'