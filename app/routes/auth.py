from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from datetime import datetime
import re

from app import db, login_manager
from app.models import User, SystemSettings

auth_bp = Blueprint('auth', __name__)

@login_manager.user_loader
def load_user(user_id):
    """加载用户"""
    return User.query.get(int(user_id))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    if request.method == 'GET':
        return render_template('auth/login.html')
    
    data = request.get_json() if request.is_json else request.form
    username = data.get('username', '').strip()
    password = data.get('password', '')
    remember = data.get('remember', False)
    
    if not username or not password:
        if request.is_json:
            return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400
        flash('用户名和密码不能为空', 'error')
        return render_template('auth/login.html')
    
    # 查找用户
    user = User.query.filter(
        (User.username == username) | (User.email == username)
    ).first()
    
    if not user or not user.check_password(password):
        if request.is_json:
            return jsonify({'success': False, 'message': '用户名或密码错误'}), 401
        flash('用户名或密码错误', 'error')
        return render_template('auth/login.html')
    
    if not user.is_active:
        if request.is_json:
            return jsonify({'success': False, 'message': '账户已被禁用'}), 403
        flash('账户已被禁用', 'error')
        return render_template('auth/login.html')
    
    # 检查维护模式
    settings = SystemSettings.get_settings()
    if settings.is_maintenance_mode() and not user.is_admin:
        if request.is_json:
            return jsonify({'success': False, 'message': '系统正在维护中'}), 503
        flash('系统正在维护中', 'error')
        return render_template('auth/login.html')
    
    # 登录用户
    login_user(user, remember=remember)
    user.update_last_login()
    db.session.commit()
    
    if request.is_json:
        return jsonify({
            'success': True,
            'message': '登录成功',
            'user': user.to_dict(),
            'redirect_url': url_for('main.dashboard')
        })
    
    next_page = request.args.get('next')
    if next_page:
        return redirect(next_page)
    
    return redirect(url_for('main.dashboard'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册"""
    settings = SystemSettings.get_settings()
    
    if not settings.is_registration_allowed():
        if request.method == 'GET':
            return render_template('auth/register_disabled.html')
        return jsonify({'success': False, 'message': '注册已关闭'}), 403
    
    if request.method == 'GET':
        return render_template('auth/register.html', 
                             require_code=bool(settings.registration_code))
    
    data = request.get_json() if request.is_json else request.form
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')
    registration_code = data.get('registration_code', '').strip()
    
    # 验证输入
    errors = []
    
    if not username:
        errors.append('用户名不能为空')
    elif len(username) < 3 or len(username) > 20:
        errors.append('用户名长度必须在3-20个字符之间')
    elif not re.match(r'^[a-zA-Z0-9_]+$', username):
        errors.append('用户名只能包含字母、数字和下划线')
    
    if not email:
        errors.append('邮箱不能为空')
    elif not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
        errors.append('邮箱格式不正确')
    
    if not password:
        errors.append('密码不能为空')
    elif len(password) < 6:
        errors.append('密码长度至少6个字符')
    
    if password != confirm_password:
        errors.append('两次输入的密码不一致')
    
    # 验证注册码
    if settings.registration_code and not settings.verify_registration_code(registration_code):
        errors.append('注册码错误')
    
    # 检查用户名和邮箱是否已存在
    if User.query.filter_by(username=username).first():
        errors.append('用户名已存在')
    
    if User.query.filter_by(email=email).first():
        errors.append('邮箱已被注册')
    
    if errors:
        if request.is_json:
            return jsonify({'success': False, 'message': '注册失败', 'errors': errors}), 400
        for error in errors:
            flash(error, 'error')
        return render_template('auth/register.html', 
                             require_code=bool(settings.registration_code))
    
    # 创建用户
    try:
        user_limits = settings.get_default_user_limits()
        user = User(
            username=username,
            email=email,
            coins=user_limits['coins'],
            max_containers=user_limits['max_containers'],
            max_ports=user_limits['max_ports'],
            max_storage=user_limits['max_storage'],
            max_cpu=user_limits['max_cpu'],
            max_memory=user_limits['max_memory']
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': '注册成功',
                'redirect_url': url_for('auth.login')
            })
        
        flash('注册成功，请登录', 'success')
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'success': False, 'message': '注册失败，请稍后重试'}), 500
        flash('注册失败，请稍后重试', 'error')
        return render_template('auth/register.html', 
                             require_code=bool(settings.registration_code))

@auth_bp.route('/logout')
@login_required
def logout():
    """用户登出"""
    logout_user()
    if request.is_json:
        return jsonify({'success': True, 'message': '已退出登录'})
    flash('已退出登录', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """用户资料"""
    if request.method == 'GET':
        if request.is_json:
            return jsonify({'success': True, 'user': current_user.to_dict()})
        return render_template('auth/profile.html', user=current_user)
    
    data = request.get_json() if request.is_json else request.form
    email = data.get('email', '').strip()
    
    errors = []
    
    if not email:
        errors.append('邮箱不能为空')
    elif not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
        errors.append('邮箱格式不正确')
    
    # 检查邮箱是否已被其他用户使用
    existing_user = User.query.filter_by(email=email).first()
    if existing_user and existing_user.id != current_user.id:
        errors.append('邮箱已被其他用户使用')
    
    if errors:
        if request.is_json:
            return jsonify({'success': False, 'message': '更新失败', 'errors': errors}), 400
        for error in errors:
            flash(error, 'error')
        return render_template('auth/profile.html', user=current_user)
    
    try:
        current_user.email = email
        db.session.commit()
        
        if request.is_json:
            return jsonify({'success': True, 'message': '资料更新成功', 'user': current_user.to_dict()})
        flash('资料更新成功', 'success')
        return render_template('auth/profile.html', user=current_user)
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'success': False, 'message': '更新失败，请稍后重试'}), 500
        flash('更新失败，请稍后重试', 'error')
        return render_template('auth/profile.html', user=current_user)

@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """修改密码"""
    data = request.get_json() if request.is_json else request.form
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')
    
    errors = []
    
    if not current_password:
        errors.append('当前密码不能为空')
    elif not current_user.check_password(current_password):
        errors.append('当前密码错误')
    
    if not new_password:
        errors.append('新密码不能为空')
    elif len(new_password) < 6:
        errors.append('新密码长度至少6个字符')
    
    if new_password != confirm_password:
        errors.append('两次输入的新密码不一致')
    
    if errors:
        if request.is_json:
            return jsonify({'success': False, 'message': '密码修改失败', 'errors': errors}), 400
        for error in errors:
            flash(error, 'error')
        return redirect(url_for('auth.profile'))
    
    try:
        current_user.set_password(new_password)
        db.session.commit()
        
        if request.is_json:
            return jsonify({'success': True, 'message': '密码修改成功'})
        flash('密码修改成功', 'success')
        return redirect(url_for('auth.profile'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'success': False, 'message': '密码修改失败，请稍后重试'}), 500
        flash('密码修改失败，请稍后重试', 'error')
        return redirect(url_for('auth.profile'))

@auth_bp.route('/api/user/info')
@login_required
def user_info():
    """获取当前用户信息API"""
    return jsonify({
        'success': True,
        'user': current_user.to_dict()
    })

@auth_bp.route('/api/user/stats')
@login_required
def user_stats():
    """获取用户统计信息API"""
    stats = {
        'container_count': current_user.get_container_count(),
        'used_ports': current_user.get_used_ports(),
        'used_storage': current_user.get_used_storage(),
        'coins': current_user.coins,
        'limits': {
            'max_containers': current_user.max_containers,
            'max_ports': current_user.max_ports,
            'max_storage': current_user.max_storage,
            'max_cpu': current_user.max_cpu,
            'max_memory': current_user.max_memory
        },
        'usage_percentage': {
            'containers': (current_user.get_container_count() / current_user.max_containers * 100) if current_user.max_containers > 0 else 0,
            'ports': (current_user.get_used_ports() / current_user.max_ports * 100) if current_user.max_ports > 0 else 0,
            'storage': (current_user.get_used_storage() / current_user.max_storage * 100) if current_user.max_storage > 0 else 0
        }
    }
    
    return jsonify({'success': True, 'stats': stats})