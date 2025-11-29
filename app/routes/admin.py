from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps

from app import db
from app.models import User, Container, Network, Template, SystemSettings, Engine
from app.container_engines.manager import engine_manager, EngineType

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            if request.is_json:
                return jsonify({'success': False, 'message': '需要管理员权限'}), 403
            flash('需要管理员权限', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """管理员仪表板"""
    # 系统统计
    stats = {
        'users': {
            'total': User.query.count(),
            'active': User.query.filter_by(is_active=True).count(),
            'admin': User.query.filter_by(is_admin=True).count()
        },
        'containers': {
            'total': Container.query.count(),
            'running': Container.query.filter_by(status='running').count(),
            'stopped': Container.query.filter(Container.status.in_(['stopped', 'exited'])).count()
        },
        'networks': {
            'total': Network.query.count(),
            'active': Network.query.filter_by(is_active=True).count()
        },
        'templates': {
            'total': Template.query.count(),
            'public': Template.query.filter_by(is_public=True).count(),
            'active': Template.query.filter_by(is_active=True).count()
        },
        'engines': len(engine_manager.list_engines())
    }
    
    return render_template('admin/dashboard.html', stats=stats)

# 用户管理
@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """用户管理页面"""
    return render_template('admin/users.html')

@admin_bp.route('/api/users', methods=['GET'])
@login_required
@admin_required
def list_users():
    """获取用户列表API"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '').strip()
    
    query = User.query
    
    if search:
        query = query.filter(
            (User.username.contains(search)) |
            (User.email.contains(search))
        )
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'success': True,
        'data': {
            'users': [u.to_dict() for u in users.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': users.total,
                'pages': users.pages,
                'has_next': users.has_next,
                'has_prev': users.has_prev
            }
        }
    })

@admin_bp.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
@admin_required
def update_user(user_id):
    """更新用户信息API"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    try:
        # 更新基本信息
        if 'email' in data:
            user.email = data['email']
        if 'is_active' in data:
            user.is_active = data['is_active']
        if 'is_admin' in data:
            user.is_admin = data['is_admin']
        
        # 更新资源限制
        if 'coins' in data:
            user.coins = data['coins']
        if 'max_containers' in data:
            user.max_containers = data['max_containers']
        if 'max_ports' in data:
            user.max_ports = data['max_ports']
        if 'max_storage' in data:
            user.max_storage = data['max_storage']
        if 'max_cpu' in data:
            user.max_cpu = data['max_cpu']
        if 'max_memory' in data:
            user.max_memory = data['max_memory']
        
        # 更新权限设置
        if 'host_privileges' in data:
            user.set_host_privileges(data['host_privileges'])
        if 'device_access' in data:
            user.set_device_access(data['device_access'])
        if 'gpu_access' in data:
            user.set_gpu_access(data['gpu_access'])
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '用户信息更新成功',
            'data': user.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'}), 500

@admin_bp.route('/api/users/<int:user_id>/password', methods=['PUT'])
@login_required
@admin_required
def reset_user_password(user_id):
    """重置用户密码API"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    new_password = data.get('password', '').strip()
    if not new_password or len(new_password) < 6:
        return jsonify({'success': False, 'message': '密码长度至少6个字符'}), 400
    
    try:
        user.set_password(new_password)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '密码重置成功'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'密码重置失败: {str(e)}'}), 500

@admin_bp.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    """删除用户API"""
    user = User.query.get_or_404(user_id)
    
    # 不能删除自己
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': '不能删除自己'}), 400
    
    # 检查用户是否有容器
    if user.get_container_count() > 0:
        return jsonify({'success': False, 'message': '用户还有容器，无法删除'}), 400
    
    try:
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '用户删除成功'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500

# 系统设置
@admin_bp.route('/settings')
@login_required
@admin_required
def settings():
    """系统设置页面"""
    return render_template('admin/settings.html')

@admin_bp.route('/api/settings', methods=['GET'])
@login_required
@admin_required
def get_settings():
    """获取系统设置API"""
    settings = SystemSettings.get_settings()
    return jsonify({
        'success': True,
        'data': settings.to_dict(include_sensitive=True)
    })

@admin_bp.route('/api/settings', methods=['PUT'])
@login_required
@admin_required
def update_settings():
    """更新系统设置API"""
    data = request.get_json()
    
    try:
        settings = SystemSettings.update_settings(data)
        return jsonify({
            'success': True,
            'message': '设置更新成功',
            'data': settings.to_dict()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'设置更新失败: {str(e)}'}), 500

# 引擎管理
@admin_bp.route('/engines')
@login_required
@admin_required
def engines():
    """引擎管理页面"""
    return render_template('admin/engines.html')

@admin_bp.route('/api/engines', methods=['POST'])
@login_required
@admin_required
def add_engine():
    """添加引擎API"""
    data = request.get_json()
    
    name = data.get('name', '').strip()
    display_name = data.get('display_name', '').strip()
    engine_type = data.get('engine_type', '').strip()
    host = data.get('host', '').strip()
    
    if not all([name, display_name, engine_type]):
        return jsonify({'success': False, 'message': '必填字段不能为空'}), 400
    
    # 检查引擎类型
    try:
        engine_type_enum = EngineType(engine_type)
    except ValueError:
        return jsonify({'success': False, 'message': '不支持的引擎类型'}), 400
    
    # 检查名称是否已存在
    if Engine.get_by_name(name):
        return jsonify({'success': False, 'message': '引擎名称已存在'}), 400
    
    try:
        # 添加到引擎管理器
        kwargs = data.get('options', {})
        success = engine_manager.add_engine(name, engine_type_enum, host, **kwargs)
        
        if not success:
            return jsonify({'success': False, 'message': '引擎连接失败'}), 500
        
        # 保存到数据库
        engine = Engine(
            name=name,
            display_name=display_name,
            engine_type=engine_type,
            host=host,
            port=data.get('port'),
            is_default=data.get('is_default', False)
        )
        
        engine.set_auth_config(data.get('auth_config', {}))
        engine.set_options(data.get('options', {}))
        
        # 如果设置为默认引擎，清除其他默认标记
        if engine.is_default:
            Engine.query.update({'is_default': False})
        
        db.session.add(engine)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '引擎添加成功',
            'data': engine.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'引擎添加失败: {str(e)}'}), 500

@admin_bp.route('/api/engines/<int:engine_id>', methods=['DELETE'])
@login_required
@admin_required
def remove_engine(engine_id):
    """删除引擎API"""
    engine = Engine.query.get_or_404(engine_id)
    
    if not engine.can_delete():
        return jsonify({'success': False, 'message': '默认引擎或有容器的引擎无法删除'}), 400
    
    try:
        # 从引擎管理器移除
        engine_manager.remove_engine(engine.actions)
        
        # 从数据库删除
        db.session.delete(engine)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '引擎删除成功'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'引擎删除失败: {str(e)}'}), 500

# 模板管理
@admin_bp.route('/templates')
@login_required
@admin_required
def templates():
    """模板管理页面"""
    return render_template('admin/templates.html')

@admin_bp.route('/api/admin/templates', methods=['GET'])
@login_required
@admin_required
def list_all_templates():
    """获取所有模板API"""
    templates = Template.query.order_by(Template.created_at.desc()).all()
    return jsonify({
        'success': True,
        'data': [t.to_dict() for t in templates]
    })

@admin_bp.route('/api/templates/<int:template_id>/toggle-public', methods=['PUT'])
@login_required
@admin_required
def toggle_template_public(template_id):
    """切换模板公开状态API"""
    template = Template.query.get_or_404(template_id)
    
    try:
        template.is_public = not template.is_public
        db.session.commit()
        
        status = '公开' if template.is_public else '私有'
        return jsonify({
            'success': True,
            'message': f'模板已设置为{status}',
            'data': template.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'操作失败: {str(e)}'}), 500

# 系统监控
@admin_bp.route('/monitor')
@login_required
@admin_required
def monitor():
    """系统监控页面"""
    return render_template('admin/monitor.html')

@admin_bp.route('/api/system/stats', methods=['GET'])
@login_required
@admin_required
def system_stats():
    """系统统计API"""
    stats = {
        'users': {
            'total': User.query.count(),
            'active': User.query.filter_by(is_active=True).count(),
            'admin': User.query.filter_by(is_admin=True).count(),
            'new_today': User.query.filter(User.created_at >= datetime.utcnow().date()).count()
        },
        'containers': {
            'total': Container.query.count(),
            'running': Container.query.filter_by(status='running').count(),
            'stopped': Container.query.filter(Container.status.in_(['stopped', 'exited'])).count(),
            'created_today': Container.query.filter(Container.created_at >= datetime.utcnow().date()).count()
        },
        'networks': {
            'total': Network.query.count(),
            'active': Network.query.filter_by(is_active=True).count()
        },
        'templates': {
            'total': Template.query.count(),
            'public': Template.query.filter_by(is_public=True).count(),
            'active': Template.query.filter_by(is_active=True).count()
        },
        'engines': {
            'total': len(engine_manager.list_engines()),
            'connected': len([e for e in engine_manager.list_engines() if e['is_connected']])
        }
    }
    
    return jsonify({'success': True, 'data': stats})