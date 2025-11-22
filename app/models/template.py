from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import json

# 使用全局db实例
from app import db

class Template(db.Model):
    """模板模型"""
    __tablename__ = 'templates'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # 模板基本信息
    name = db.Column(db.String(255), nullable=False, index=True)  # 模板名称
    display_name = db.Column(db.String(255), nullable=False)  # 显示名称
    description = db.Column(db.Text)  # 模板描述
    category = db.Column(db.String(100), default='general')  # 模板分类
    
    # 模板类型
    template_type = db.Column(db.String(50), nullable=False)  # image, dockerfile, compose
    
    # 镜像信息（用于image类型）
    image_name = db.Column(db.String(255))  # 镜像名称
    image_tag = db.Column(db.String(100), default='latest')  # 镜像标签
    
    # Dockerfile信息（用于dockerfile类型）
    dockerfile_content = db.Column(db.Text)  # Dockerfile内容
    build_args = db.Column(db.Text, default='{}')  # 构建参数
    
    # Docker Compose信息（用于compose类型）
    compose_content = db.Column(db.Text)  # docker-compose.yml内容
    
    # 默认配置
    default_config = db.Column(db.Text, default='{}')  # 默认容器配置
    
    # 模板状态
    is_active = db.Column(db.Boolean, default=True)  # 是否激活
    is_public = db.Column(db.Boolean, default=False)  # 是否公开
    
    # 统计信息
    usage_count = db.Column(db.Integer, default=0)  # 使用次数
    
    # 版本信息
    version = db.Column(db.String(50), default='1.0.0')  # 模板版本
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # 外键关系
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 创建者
    
    # 关系
    creator = db.relationship('User', backref='created_templates')
    
    def __init__(self, **kwargs):
        super(Template, self).__init__(**kwargs)
        if not self.default_config:
            self.default_config = '{}'
        if not self.build_args:
            self.build_args = '{}'
    
    def get_default_config(self):
        """获取默认配置"""
        try:
            return json.loads(self.default_config)
        except:
            return {}
    
    def set_default_config(self, config):
        """设置默认配置"""
        self.default_config = json.dumps(config)
    
    def get_build_args(self):
        """获取构建参数"""
        try:
            return json.loads(self.build_args)
        except:
            return {}
    
    def set_build_args(self, args):
        """设置构建参数"""
        self.build_args = json.dumps(args)
    
    def get_full_image_name(self):
        """获取完整镜像名称"""
        if self.template_type == 'image' and self.image_name:
            return f"{self.image_name}:{self.image_tag}"
        return None
    
    def increment_usage(self):
        """增加使用次数"""
        self.usage_count += 1
    
    def is_image_template(self):
        """检查是否为镜像模板"""
        return self.template_type == 'image'
    
    def is_dockerfile_template(self):
        """检查是否为Dockerfile模板"""
        return self.template_type == 'dockerfile'
    
    def is_compose_template(self):
        """检查是否为Compose模板"""
        return self.template_type == 'compose'
    
    def can_edit(self, user_id):
        """检查用户是否可以编辑此模板"""
        return self.created_by == user_id
    
    def can_delete(self, user_id):
        """检查用户是否可以删除此模板"""
        return self.created_by == user_id and len(self.containers) == 0
    
    def to_dict(self, include_content=False):
        """转换为字典"""
        data = {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'category': self.category,
            'template_type': self.template_type,
            'is_active': self.is_active,
            'is_public': self.is_public,
            'usage_count': self.usage_count,
            'version': self.version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'creator_name': self.creator.username if self.creator else None,
            'default_config': self.get_default_config()
        }
        
        # 根据模板类型添加相应信息
        if self.template_type == 'image':
            data.update({
                'image_name': self.image_name,
                'image_tag': self.image_tag,
                'full_image_name': self.get_full_image_name()
            })
        
        if include_content:
            if self.template_type == 'dockerfile':
                data.update({
                    'dockerfile_content': self.dockerfile_content,
                    'build_args': self.get_build_args()
                })
            elif self.template_type == 'compose':
                data['compose_content'] = self.compose_content
        
        return data
    
    @staticmethod
    def get_by_name(name):
        """根据名称获取模板"""
        return Template.query.filter_by(name=name).first()
    
    @staticmethod
    def get_public_templates():
        """获取公开模板"""
        return Template.query.filter_by(is_public=True, is_active=True).all()
    
    @staticmethod
    def get_user_templates(user_id):
        """获取用户创建的模板"""
        return Template.query.filter_by(created_by=user_id).all()
    
    @staticmethod
    def get_available_templates(user_id):
        """获取用户可用的模板（公开模板 + 用户自己的模板）"""
        return Template.query.filter(
            db.or_(
                Template.is_public == True,
                Template.created_by == user_id
            )
        ).filter_by(is_active=True).all()
    
    @staticmethod
    def get_by_category(category):
        """根据分类获取模板"""
        return Template.query.filter_by(category=category, is_active=True).all()
    
    @staticmethod
    def get_popular_templates(limit=10):
        """获取热门模板"""
        return Template.query.filter_by(is_active=True).order_by(
            Template.usage_count.desc()
        ).limit(limit).all()
    
    @staticmethod
    def search_templates(keyword, user_id=None):
        """搜索模板"""
        query = Template.query.filter(
            db.or_(
                Template.name.contains(keyword),
                Template.display_name.contains(keyword),
                Template.description.contains(keyword)
            )
        ).filter_by(is_active=True)
        
        if user_id:
            query = query.filter(
                db.or_(
                    Template.is_public == True,
                    Template.created_by == user_id
                )
            )
        else:
            query = query.filter_by(is_public=True)
        
        return query.all()
    
    @staticmethod
    def get_categories():
        """获取所有模板分类"""
        categories = db.session.query(Template.category).distinct().all()
        return [category[0] for category in categories]
    
    @staticmethod
    def count_templates_by_type():
        """按类型统计模板数量"""
        return db.session.query(
            Template.template_type,
            db.func.count(Template.id)
        ).filter_by(is_active=True).group_by(Template.template_type).all()
    
    def __repr__(self):
        return f'<Template {self.name}>'