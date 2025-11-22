from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from app import db
from app.models import User, Container, Network, Template, SystemSettings, Engine
from app.container_engines.manager import engine_manager

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """首页"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    settings = SystemSettings.get_settings()
    
    # 获取系统统计信息
    stats = {
        'total_users': User.query.filter_by(is_active=True).count(),
        'total_containers': Container.query.count(),
        'running_containers': Container.query.filter_by(status='running').count(),
        'total_templates': Template.query.filter_by(is_active=True, is_public=True).count()
    }
    
    return render_template('index.html', stats=stats, settings=settings)

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """用户仪表板"""
    # 获取用户容器统计
    user_containers = Container.get_user_containers(current_user.id)
    container_stats = {
        'total': len(user_containers),
        'running': len([c for c in user_containers if c.status == 'running']),
        'stopped': len([c for c in user_containers if c.status in ['stopped', 'exited']]),
        'created': len([c for c in user_containers if c.status == 'created'])
    }
    
    # 获取用户网络统计
    user_networks = Network.get_user_networks(current_user.id)
    network_stats = {
        'total': len(user_networks),
        'active': len([n for n in user_networks if n.is_active])
    }
    
    # 获取资源使用情况
    resource_usage = {
        'containers': {
            'used': container_stats['total'],
            'limit': current_user.max_containers,
            'percentage': (container_stats['total'] / current_user.max_containers * 100) if current_user.max_containers > 0 else 0
        },
        'ports': {
            'used': current_user.get_used_ports(),
            'limit': current_user.max_ports,
            'percentage': (current_user.get_used_ports() / current_user.max_ports * 100) if current_user.max_ports > 0 else 0
        },
        'storage': {
            'used': current_user.get_used_storage(),
            'limit': current_user.max_storage,
            'percentage': (current_user.get_used_storage() / current_user.max_storage * 100) if current_user.max_storage > 0 else 0
        }
    }
    
    # 获取最近的容器
    recent_containers = Container.query.filter_by(user_id=current_user.id)\
        .order_by(Container.updated_at.desc()).limit(5).all()
    
    # 获取引擎状态
    engine_status = engine_manager.health_check()
    
    if request.is_json:
        return jsonify({
            'success': True,
            'data': {
                'container_stats': container_stats,
                'network_stats': network_stats,
                'resource_usage': resource_usage,
                'recent_containers': [c.to_dict(include_config=False) for c in recent_containers],
                'engine_status': engine_status,
                'user_info': current_user.to_dict()
            }
        })
    
    return render_template('dashboard.html',
                         container_stats=container_stats,
                         network_stats=network_stats,
                         resource_usage=resource_usage,
                         recent_containers=recent_containers,
                         engine_status=engine_status)

@main_bp.route('/containers')
@login_required
def containers():
    """容器管理页面"""
    # 获取可用引擎用于筛选
    engines = engine_manager.list_engines()
    return render_template('containers/list.html', engines=engines)

@main_bp.route('/containers/create')
@login_required
def create_container():
    """创建容器页面"""
    # 获取可用模板
    templates = Template.get_available_templates(current_user.id)
    
    # 获取用户网络
    networks = Network.get_user_networks(current_user.id)
    
    # 获取可用引擎
    engines = engine_manager.list_engines()
    
    return render_template('containers/create.html',
                         templates=templates,
                         networks=networks,
                         engines=engines)

@main_bp.route('/containers/<int:container_id>')
@login_required
def container_detail(container_id):
    """容器详情页面"""
    container = Container.query.get_or_404(container_id)
    
    # 检查权限
    if container.user_id != current_user.id and not current_user.is_admin:
        return render_template('errors/403.html'), 403
    
    return render_template('containers/detail.html', container=container)

@main_bp.route('/networks')
@login_required
def networks():
    """网络管理页面"""
    return render_template('networks/list.html')

@main_bp.route('/networks/create')
@login_required
def create_network():
    """创建网络页面"""
    # 获取可用引擎
    engines = engine_manager.list_engines()
    
    return render_template('networks/create.html', engines=engines)

@main_bp.route('/templates')
@login_required
def templates():
    """模板管理页面"""
    return render_template('templates/list.html')

@main_bp.route('/templates/create')
@login_required
def create_template():
    """创建模板页面"""
    return render_template('templates/create.html')

@main_bp.route('/templates/<int:template_id>')
@login_required
def template_detail(template_id):
    """模板详情页面"""
    template = Template.query.get_or_404(template_id)
    
    # 检查权限
    if not template.is_public and template.created_by != current_user.id and not current_user.is_admin:
        return render_template('errors/403.html'), 403
    
    return render_template('templates/detail.html', template=template)

@main_bp.route('/files')
@login_required
def files():
    """文件管理页面"""
    return render_template('files/browser.html')

@main_bp.route('/terminal')
@login_required
def terminal():
    """终端页面"""
    container_id = request.args.get('container_id')
    if not container_id:
        return redirect(url_for('main.containers'))
    
    container = Container.query.get_or_404(container_id)
    
    # 检查权限
    if container.user_id != current_user.id and not current_user.is_admin:
        return render_template('errors/403.html'), 403
    
    return render_template('terminal.html', container=container)

@main_bp.route('/api/system/status')
@login_required
def system_status():
    """系统状态API"""
    # 获取引擎状态
    engine_status = engine_manager.health_check()
    engines_info = engine_manager.list_engines()
    
    # 获取系统统计
    system_stats = {
        'total_users': User.query.filter_by(is_active=True).count(),
        'total_containers': Container.query.count(),
        'running_containers': Container.query.filter_by(status='running').count(),
        'total_networks': Network.query.count(),
        'total_templates': Template.query.filter_by(is_active=True).count(),
        'total_engines': len(engines_info),
        'connected_engines': len([e for e in engines_info if e['is_connected']])
    }
    
    return jsonify({
        'success': True,
        'data': {
            'engine_status': engine_status,
            'engines_info': engines_info,
            'system_stats': system_stats
        }
    })

@main_bp.route('/api/dashboard/stats')
@login_required
def dashboard_stats():
    """仪表板统计API"""
    if current_user.is_admin:
        # 管理员看到全局统计
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
            'engines': engine_manager.get_all_system_info()
        }
    else:
        # 普通用户看到个人统计
        user_containers = Container.get_user_containers(current_user.id)
        user_networks = Network.get_user_networks(current_user.id)
        
        stats = {
            'containers': {
                'total': len(user_containers),
                'running': len([c for c in user_containers if c.status == 'running']),
                'stopped': len([c for c in user_containers if c.status in ['stopped', 'exited']])
            },
            'networks': {
                'total': len(user_networks),
                'active': len([n for n in user_networks if n.is_active])
            },
            'resources': {
                'containers_used': len(user_containers),
                'containers_limit': current_user.max_containers,
                'ports_used': current_user.get_used_ports(),
                'ports_limit': current_user.max_ports,
                'storage_used': current_user.get_used_storage(),
                'storage_limit': current_user.max_storage,
                'coins': current_user.coins
            }
        }
    
    return jsonify({'success': True, 'stats': stats})

@main_bp.route('/api/recent-activity')
@login_required
def recent_activity():
    """最近活动API"""
    activities = []
    
    if current_user.is_admin:
        # 管理员看到全局活动
        recent_containers = Container.query.order_by(Container.updated_at.desc()).limit(10).all()
        recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
        
        for container in recent_containers:
            activities.append({
                'type': 'container',
                'action': f"容器 {container.name} 状态变更为 {container.status}",
                'time': container.updated_at.isoformat(),
                'user': container.owner.username
            })
        
        for user in recent_users:
            activities.append({
                'type': 'user',
                'action': f"新用户 {user.username} 注册",
                'time': user.created_at.isoformat(),
                'user': user.username
            })
    else:
        # 普通用户看到个人活动
        recent_containers = Container.query.filter_by(user_id=current_user.id)\
            .order_by(Container.updated_at.desc()).limit(10).all()
        
        for container in recent_containers:
            activities.append({
                'type': 'container',
                'action': f"容器 {container.name} 状态变更为 {container.status}",
                'time': container.updated_at.isoformat(),
                'user': current_user.username
            })
    
    # 按时间排序
    activities.sort(key=lambda x: x['time'], reverse=True)
    
    return jsonify({'success': True, 'activities': activities[:20]})

@main_bp.errorhandler(404)
def not_found(error):
    """404错误处理"""
    if request.is_json:
        return jsonify({'success': False, 'message': '页面不存在'}), 404
    return render_template('errors/404.html'), 404

@main_bp.errorhandler(403)
def forbidden(error):
    """403错误处理"""
    if request.is_json:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    return render_template('errors/403.html'), 403

@main_bp.errorhandler(500)
def internal_error(error):
    """500错误处理"""
    db.session.rollback()
    if request.is_json:
        return jsonify({'success': False, 'message': '服务器内部错误'}), 500
    return render_template('errors/500.html'), 500