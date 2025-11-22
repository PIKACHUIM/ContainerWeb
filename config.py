import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///containerweb.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT配置
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    
    # 上传配置
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # 系统默认设置
    DEFAULT_MAX_CONTAINERS = 10
    DEFAULT_MAX_PORTS = 20
    DEFAULT_MAX_STORAGE = 10  # GB
    DEFAULT_MAX_CPU = 2.0  # CPU cores
    DEFAULT_MAX_MEMORY = 4096  # MB
    DEFAULT_COINS = 100
    
    # 容器引擎配置
    DOCKER_HOST = os.environ.get('DOCKER_HOST') or 'unix://var/run/docker.sock'
    PODMAN_HOST = os.environ.get('PODMAN_HOST') or 'unix://run/podman/podman.sock'
    
    # 网络配置
    NETWORK_SUBNET_BASE = '172.20.0.0/16'
    
    # 安全配置
    ALLOW_REGISTRATION = os.environ.get('ALLOW_REGISTRATION', 'true').lower() == 'true'
    REGISTRATION_CODE = os.environ.get('REGISTRATION_CODE') or ''

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or 'sqlite:///containerweb_dev.db'

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///containerweb.db'

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}