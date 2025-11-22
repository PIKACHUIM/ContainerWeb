from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import json

from app import db
from app.models import Container, Network, Template, Engine
from app.container_engines.manager import engine_manager, EngineType
from app.container_engines.base import ContainerConfig

api_bp = Blueprint('api', __name__)

# 容器管理API
@api_bp.route('/containers/user', methods=['GET'])
@login_required
def get_user_containers_api():
    """获取用户容器列表（增强版）"""
    # 获取查询参数
    status = request.args.get('status')
    engine_name = request.args.get('engine')
    search = request.args.get('search', '').strip()
    
    # 获取用户容器
    if current_user.is_admin:
        # 管理员获取所有容器
        query = Container.query
    else:
        # 普通用户只获取自己的容器
        query = Container.query.filter_by(user_id=current_user.id)
    
    # 应用筛选条件
    if status:
        query = query.filter_by(status=status)
    
    if engine_name:
        query = query.filter_by(engine_name=engine_name)
    
    if search:
        # 搜索容器名称或镜像名称
        query = query.filter(
            db.or_(
                Container.name.contains(search),
                Container.image.contains(search)
            )
        )
    
    # 获取所有容器（用于统计）
    all_containers = query.all()
    
    # 更新容器状态（从引擎获取实时信息）
    for container in all_containers:
        try:
            engine_container = engine_manager.get_container(container.container_id, container.engine_name)
            if engine_container:
                container.update_status(engine_container.status)
                container.ip_address = engine_container.ip_address
                container.update_stats(engine_container.cpu_usage, engine_container.memory_usage)
        except Exception as e:
            # 如果获取引擎信息失败，使用数据库中的状态
            pass
    
    db.session.commit()
    
    # 计算统计信息
    stats = {
        'total': len(all_containers),
        'running': len([c for c in all_containers if c.status == 'running']),
        'stopped': len([c for c in all_containers if c.status in ['stopped', 'exited']]),
        'paused': len([c for c in all_containers if c.status == 'paused'])
    }
    
    # 计算资源使用
    total_cpu = sum(c.cpu_limit or 0 for c in all_containers if c.cpu_limit)
    total_memory = sum(c.memory_limit or 0 for c in all_containers if c.memory_limit)
    
    # 返回数据
    return jsonify({
        'success': True,
        'data': {
            'containers': [c.to_dict() for c in all_containers],
            'stats': stats,
            'resource_usage': {
                'total_cpu': total_cpu,
                'total_memory': total_memory
            }
        }
    })

@api_bp.route('/containers', methods=['GET'])
@login_required
def list_containers():
    """获取容器列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    engine_name = request.args.get('engine')
    
    query = Container.query
    
    # 非管理员只能看到自己的容器
    if not current_user.is_admin:
        query = query.filter_by(user_id=current_user.id)
    
    # 状态过滤
    if status:
        query = query.filter_by(status=status)
    
    # 引擎过滤
    if engine_name:
        query = query.filter_by(engine_name=engine_name)
    
    # 分页
    containers = query.order_by(Container.updated_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'success': True,
        'data': {
            'containers': [c.to_dict() for c in containers.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': containers.total,
                'pages': containers.pages,
                'has_next': containers.has_next,
                'has_prev': containers.has_prev
            }
        }
    })

@api_bp.route('/containers', methods=['POST'])
@login_required
def create_container():
    """创建容器"""
    data = request.get_json()
    
    # 验证输入
    required_fields = ['name', 'image']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'success': False, 'message': f'{field} 不能为空'}), 400
    
    name = data['name'].strip()
    image = data['image'].strip()
    engine_name = data.get('engine_name')
    template_id = data.get('template_id')
    
    # 检查容器名称是否已存在
    if Container.get_by_name(name):
        return jsonify({'success': False, 'message': '容器名称已存在'}), 400
    
    # 检查用户是否可以创建容器
    if not current_user.can_create_container():
        return jsonify({'success': False, 'message': '已达到最大容器数量限制'}), 403
    
    # 检查端口限制
    port_mappings = data.get('port_mappings', {})
    if not current_user.can_use_ports(len(port_mappings)):
        return jsonify({'success': False, 'message': '端口数量超出限制'}), 403
    
    try:
        # 构建容器配置
        config = ContainerConfig(
            name=name,
            image=image,
            ports=port_mappings,
            volumes=data.get('volume_mappings', {}),
            environment=data.get('environment_vars', {}),
            network=data.get('network'),
            cpu_limit=data.get('cpu_limit'),
            memory_limit=data.get('memory_limit'),
            privileged=data.get('privileged', False),
            devices=data.get('devices', []),
            command=data.get('command'),
            working_dir=data.get('working_dir'),
            user=data.get('user'),
            restart_policy=data.get('restart_policy', 'no')
        )
        
        # 创建容器
        container_id = engine_manager.create_container(config, engine_name)
        if not container_id:
            return jsonify({'success': False, 'message': '容器创建失败'}), 500
        
        # 保存到数据库
        container = Container(
            container_id=container_id,
            name=name,
            image=image,
            engine_name=engine_name or engine_manager.get_default_engine_name(),
            user_id=current_user.id,
            template_id=template_id,
            cpu_limit=config.cpu_limit,
            memory_limit=config.memory_limit,
            privileged=config.privileged,
            command=config.command,
            working_dir=config.working_dir,
            user=config.user,
            restart_policy=config.restart_policy
        )
        
        container.set_port_mappings(port_mappings)
        container.set_volume_mappings(data.get('volume_mappings', {}))
        container.set_environment_vars(data.get('environment_vars', {}))
        container.set_devices(data.get('devices', []))
        
        # 处理网络
        if data.get('network_id'):
            network = Network.query.get(data['network_id'])
            if network and (network.user_id == current_user.id or current_user.is_admin):
                container.network_id = network.id
        
        db.session.add(container)
        db.session.commit()
        
        # 增加模板使用次数
        if template_id:
            template = Template.query.get(template_id)
            if template:
                template.increment_usage()
                db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '容器创建成功',
            'data': container.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'容器创建失败: {str(e)}'}), 500

@api_bp.route('/containers/<int:container_id>', methods=['GET'])
@login_required
def get_container(container_id):
    """获取容器详情"""
    container = Container.query.get_or_404(container_id)
    
    # 检查权限
    if container.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    # 从引擎获取实时状态
    engine_container = engine_manager.get_container(container.container_id, container.engine_name)
    if engine_container:
        container.update_status(engine_container.status)
        container.ip_address = engine_container.ip_address
        container.update_stats(engine_container.cpu_usage, engine_container.memory_usage)
        db.session.commit()
    
    return jsonify({
        'success': True,
        'data': container.to_dict()
    })

@api_bp.route('/containers/<int:container_id>/start', methods=['POST'])
@login_required
def start_container(container_id):
    """启动容器"""
    container = Container.query.get_or_404(container_id)
    
    # 检查权限
    if container.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    if not container.can_start():
        return jsonify({'success': False, 'message': '容器当前状态不允许启动'}), 400
    
    try:
        success = engine_manager.start_container(container.container_id, container.engine_name)
        if success:
            container.update_status('running')
            db.session.commit()
            return jsonify({'success': True, 'message': '容器启动成功'})
        else:
            return jsonify({'success': False, 'message': '容器启动失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'容器启动失败: {str(e)}'}), 500

@api_bp.route('/containers/<int:container_id>/stop', methods=['POST'])
@login_required
def stop_container(container_id):
    """停止容器"""
    container = Container.query.get_or_404(container_id)
    
    # 检查权限
    if container.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    if not container.can_stop():
        return jsonify({'success': False, 'message': '容器当前状态不允许停止'}), 400
    
    try:
        timeout = request.json.get('timeout', 10) if request.is_json else 10
        success = engine_manager.stop_container(container.container_id, timeout, container.engine_name)
        if success:
            container.update_status('stopped')
            db.session.commit()
            return jsonify({'success': True, 'message': '容器停止成功'})
        else:
            return jsonify({'success': False, 'message': '容器停止失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'容器停止失败: {str(e)}'}), 500

@api_bp.route('/containers/<int:container_id>/restart', methods=['POST'])
@login_required
def restart_container(container_id):
    """重启容器"""
    container = Container.query.get_or_404(container_id)
    
    # 检查权限
    if container.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    try:
        timeout = request.json.get('timeout', 10) if request.is_json else 10
        success = engine_manager.restart_container(container.container_id, timeout, container.engine_name)
        if success:
            container.update_status('running')
            db.session.commit()
            return jsonify({'success': True, 'message': '容器重启成功'})
        else:
            return jsonify({'success': False, 'message': '容器重启失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'容器重启失败: {str(e)}'}), 500

@api_bp.route('/containers/<int:container_id>', methods=['DELETE'])
@login_required
def delete_container(container_id):
    """删除容器"""
    container = Container.query.get_or_404(container_id)
    
    # 检查权限
    if container.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    try:
        force = request.json.get('force', False) if request.is_json else False
        
        # 从引擎删除容器
        success = engine_manager.remove_container(container.container_id, force, container.engine_name)
        if success or force:
            # 从数据库删除
            db.session.delete(container)
            db.session.commit()
            return jsonify({'success': True, 'message': '容器删除成功'})
        else:
            return jsonify({'success': False, 'message': '容器删除失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'容器删除失败: {str(e)}'}), 500

@api_bp.route('/containers/batch/start', methods=['POST'])
@login_required
def batch_start_containers():
    """批量启动容器"""
    data = request.get_json()
    container_ids = data.get('container_ids', [])
    
    if not container_ids:
        return jsonify({'success': False, 'message': '未选择容器'}), 400
    
    results = []
    success_count = 0
    
    for container_id in container_ids:
        try:
            container = Container.query.get(container_id)
            if not container:
                results.append({'id': container_id, 'success': False, 'message': '容器不存在'})
                continue
            
            # 检查权限
            if container.user_id != current_user.id and not current_user.is_admin:
                results.append({'id': container_id, 'success': False, 'message': '权限不足'})
                continue
            
            if not container.can_start():
                results.append({'id': container_id, 'success': False, 'message': '容器当前状态不允许启动'})
                continue
            
            success = engine_manager.start_container(container.container_id, container.engine_name)
            if success:
                container.update_status('running')
                success_count += 1
                results.append({'id': container_id, 'success': True, 'message': '容器启动成功'})
            else:
                results.append({'id': container_id, 'success': False, 'message': '容器启动失败'})
        except Exception as e:
            results.append({'id': container_id, 'success': False, 'message': f'容器启动失败: {str(e)}'})
    
    db.session.commit()
    
    return jsonify({
        'success': success_count > 0,
        'message': f'批量启动完成，成功 {success_count}/{len(container_ids)} 个容器',
        'data': {'results': results, 'success_count': success_count}
    })

@api_bp.route('/containers/batch/stop', methods=['POST'])
@login_required
def batch_stop_containers():
    """批量停止容器"""
    data = request.get_json()
    container_ids = data.get('container_ids', [])
    timeout = data.get('timeout', 10)
    
    if not container_ids:
        return jsonify({'success': False, 'message': '未选择容器'}), 400
    
    results = []
    success_count = 0
    
    for container_id in container_ids:
        try:
            container = Container.query.get(container_id)
            if not container:
                results.append({'id': container_id, 'success': False, 'message': '容器不存在'})
                continue
            
            # 检查权限
            if container.user_id != current_user.id and not current_user.is_admin:
                results.append({'id': container_id, 'success': False, 'message': '权限不足'})
                continue
            
            if not container.can_stop():
                results.append({'id': container_id, 'success': False, 'message': '容器当前状态不允许停止'})
                continue
            
            success = engine_manager.stop_container(container.container_id, timeout, container.engine_name)
            if success:
                container.update_status('stopped')
                success_count += 1
                results.append({'id': container_id, 'success': True, 'message': '容器停止成功'})
            else:
                results.append({'id': container_id, 'success': False, 'message': '容器停止失败'})
        except Exception as e:
            results.append({'id': container_id, 'success': False, 'message': f'容器停止失败: {str(e)}'})
    
    db.session.commit()
    
    return jsonify({
        'success': success_count > 0,
        'message': f'批量停止完成，成功 {success_count}/{len(container_ids)} 个容器',
        'data': {'results': results, 'success_count': success_count}
    })

@api_bp.route('/containers/batch/restart', methods=['POST'])
@login_required
def batch_restart_containers():
    """批量重启容器"""
    data = request.get_json()
    container_ids = data.get('container_ids', [])
    timeout = data.get('timeout', 10)
    
    if not container_ids:
        return jsonify({'success': False, 'message': '未选择容器'}), 400
    
    results = []
    success_count = 0
    
    for container_id in container_ids:
        try:
            container = Container.query.get(container_id)
            if not container:
                results.append({'id': container_id, 'success': False, 'message': '容器不存在'})
                continue
            
            # 检查权限
            if container.user_id != current_user.id and not current_user.is_admin:
                results.append({'id': container_id, 'success': False, 'message': '权限不足'})
                continue
            
            success = engine_manager.restart_container(container.container_id, timeout, container.engine_name)
            if success:
                container.update_status('running')
                success_count += 1
                results.append({'id': container_id, 'success': True, 'message': '容器重启成功'})
            else:
                results.append({'id': container_id, 'success': False, 'message': '容器重启失败'})
        except Exception as e:
            results.append({'id': container_id, 'success': False, 'message': f'容器重启失败: {str(e)}'})
    
    db.session.commit()
    
    return jsonify({
        'success': success_count > 0,
        'message': f'批量重启完成，成功 {success_count}/{len(container_ids)} 个容器',
        'data': {'results': results, 'success_count': success_count}
    })

@api_bp.route('/containers/batch/delete', methods=['POST'])
@login_required
def batch_delete_containers():
    """批量删除容器"""
    data = request.get_json()
    container_ids = data.get('container_ids', [])
    force = data.get('force', False)
    
    if not container_ids:
        return jsonify({'success': False, 'message': '未选择容器'}), 400
    
    results = []
    success_count = 0
    
    for container_id in container_ids:
        try:
            container = Container.query.get(container_id)
            if not container:
                results.append({'id': container_id, 'success': False, 'message': '容器不存在'})
                continue
            
            # 检查权限
            if container.user_id != current_user.id and not current_user.is_admin:
                results.append({'id': container_id, 'success': False, 'message': '权限不足'})
                continue
            
            # 从引擎删除容器
            success = engine_manager.remove_container(container.container_id, force, container.engine_name)
            if success or force:
                # 从数据库删除
                db.session.delete(container)
                success_count += 1
                results.append({'id': container_id, 'success': True, 'message': '容器删除成功'})
            else:
                results.append({'id': container_id, 'success': False, 'message': '容器删除失败'})
        except Exception as e:
            results.append({'id': container_id, 'success': False, 'message': f'容器删除失败: {str(e)}'})
    
    db.session.commit()
    
    return jsonify({
        'success': success_count > 0,
        'message': f'批量删除完成，成功 {success_count}/{len(container_ids)} 个容器',
        'data': {'results': results, 'success_count': success_count}
    })

@api_bp.route('/containers/<int:container_id>/logs', methods=['GET'])
@login_required
def get_container_logs(container_id):
    """获取容器日志"""
    container = Container.query.get_or_404(container_id)
    
    # 检查权限
    if container.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    try:
        tail = request.args.get('tail', 100, type=int)
        logs = engine_manager.get_container_logs(container.container_id, tail, container.engine_name)
        
        return jsonify({
            'success': True,
            'data': {
                'logs': logs,
                'container_name': container.name
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取日志失败: {str(e)}'}), 500

@api_bp.route('/containers/<int:container_id>/exec', methods=['POST'])
@login_required
def exec_container_command(container_id):
    """在容器中执行命令"""
    container = Container.query.get_or_404(container_id)
    
    # 检查权限
    if container.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    data = request.get_json()
    command = data.get('command', '').strip()
    
    if not command:
        return jsonify({'success': False, 'message': '命令不能为空'}), 400
    
    try:
        result = engine_manager.exec_command(container.container_id, command, container.engine_name)
        
        return jsonify({
            'success': True,
            'data': {
                'exit_code': result['exit_code'],
                'output': result['output']
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'命令执行失败: {str(e)}'}), 500

# 网络管理API
@api_bp.route('/networks', methods=['GET'])
@login_required
def list_networks():
    """获取网络列表"""
    # 获取查询参数
    network_type = request.args.get('type')
    status = request.args.get('status')
    search = request.args.get('search')
    
    if current_user.is_admin:
        query = Network.query
    else:
        query = Network.query.filter(Network.user_id == current_user.id)
    
    # 应用筛选条件
    if network_type:
        query = query.filter(Network.driver == network_type)
    
    if status:
        is_active = status.lower() == 'active'
        query = query.filter(Network.is_active == is_active)
    
    if search:
        query = query.filter(Network.name.contains(search))
    
    networks = query.all()
    
    return jsonify({
        'success': True,
        'data': [n.to_dict() for n in networks]
    })

@api_bp.route('/networks/user', methods=['GET'])
@login_required
def get_user_networks():
    """获取用户网络列表（带统计信息）"""
    try:
        # 获取查询参数
        network_type = request.args.get('type')
        status = request.args.get('status')
        search = request.args.get('search')
        
        # 基础查询
        if current_user.is_admin:
            query = Network.query
        else:
            query = Network.query.filter(Network.user_id == current_user.id)
        
        # 应用筛选条件
        if network_type:
            query = query.filter(Network.driver == network_type)
        
        if status:
            is_active = status.lower() == 'active'
            query = query.filter(Network.is_active == is_active)
        
        if search:
            query = query.filter(Network.name.contains(search))
        
        networks = query.all()
        
        # 计算统计信息
        total_networks = len(networks)
        active_networks = sum(1 for n in networks if n.is_active)
        bridge_networks = sum(1 for n in networks if n.driver == 'bridge')
        overlay_networks = sum(1 for n in networks if n.driver == 'overlay')
        
        return jsonify({
            'success': True,
            'data': {
                'networks': [n.to_dict() for n in networks],
                'statistics': {
                    'total': total_networks,
                    'active': active_networks,
                    'bridge': bridge_networks,
                    'overlay': overlay_networks
                }
            }
        })
        
    except Exception as e:
        current_app.logger.error(f'获取用户网络列表失败: {str(e)}')
        return jsonify({
            'success': False,
            'message': '获取网络列表失败'
        }), 500

@api_bp.route('/networks', methods=['POST'])
@login_required
def create_network():
    """创建网络"""
    data = request.get_json()
    
    name = data.get('name', '').strip()
    driver = data.get('driver', 'bridge')
    subnet = data.get('subnet', '').strip()
    engine_name = data.get('engine_name')
    
    if not name:
        return jsonify({'success': False, 'message': '网络名称不能为空'}), 400
    
    # 生成完整网络名称（用户ID_网络名称）
    full_name = Network.generate_network_name(current_user.id, name)
    
    # 检查名称是否可用
    if not Network.is_name_available(name, current_user.id):
        return jsonify({'success': False, 'message': '网络名称已存在'}), 400
    
    try:
        # 在引擎中创建网络
        network_id = engine_manager.create_network(full_name, driver, subnet, engine_name)
        if not network_id:
            return jsonify({'success': False, 'message': '网络创建失败'}), 500
        
        # 保存到数据库
        network = Network(
            network_id=network_id,
            name=name,
            engine_name=engine_name or engine_manager.get_default_engine_name(),
            driver=driver,
            subnet=subnet,
            user_id=current_user.id
        )
        
        db.session.add(network)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '网络创建成功',
            'data': network.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'网络创建失败: {str(e)}'}), 500

@api_bp.route('/networks/<int:network_id>', methods=['DELETE'])
@login_required
def delete_network(network_id):
    """删除网络"""
    network = Network.query.get_or_404(network_id)
    
    # 检查权限
    if network.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    if not network.can_delete():
        return jsonify({'success': False, 'message': '网络正在使用中，无法删除'}), 400
    
    try:
        # 从引擎删除网络
        success = engine_manager.remove_network(network.network_id, network.engine_name)
        if success:
            # 从数据库删除
            db.session.delete(network)
            db.session.commit()
            return jsonify({'success': True, 'message': '网络删除成功'})
        else:
            return jsonify({'success': False, 'message': '网络删除失败'}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'网络删除失败: {str(e)}'}), 500

@api_bp.route('/networks/batch/delete', methods=['POST'])
@login_required
def batch_delete_networks():
    """批量删除网络"""
    data = request.get_json()
    network_ids = data.get('network_ids', [])
    
    if not network_ids:
        return jsonify({'success': False, 'message': '未选择网络'}), 400
    
    results = []
    success_count = 0
    
    for network_id in network_ids:
        try:
            network = Network.query.get(network_id)
            if not network:
                results.append({'id': network_id, 'success': False, 'message': '网络不存在'})
                continue
            
            # 检查权限
            if network.user_id != current_user.id and not current_user.is_admin:
                results.append({'id': network_id, 'success': False, 'message': '权限不足'})
                continue
            
            if not network.can_delete():
                results.append({'id': network_id, 'success': False, 'message': '网络正在使用中，无法删除'})
                continue
            
            # 从引擎删除网络
            success = engine_manager.remove_network(network.network_id, network.engine_name)
            if success:
                # 从数据库删除
                db.session.delete(network)
                success_count += 1
                results.append({'id': network_id, 'success': True, 'message': '网络删除成功'})
            else:
                results.append({'id': network_id, 'success': False, 'message': '网络删除失败'})
        except Exception as e:
            results.append({'id': network_id, 'success': False, 'message': f'网络删除失败: {str(e)}'})
    
    if success_count > 0:
        db.session.commit()
    else:
        db.session.rollback()
    
    return jsonify({
        'success': success_count > 0,
        'message': f'批量删除完成，成功 {success_count}/{len(network_ids)} 个网络',
        'data': {'results': results, 'success_count': success_count}
    })

@api_bp.route('/networks/<int:network_id>/activate', methods=['POST'])
@login_required
def activate_network(network_id):
    """激活网络"""
    network = Network.query.get_or_404(network_id)
    
    # 检查权限
    if network.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    if network.is_active:
        return jsonify({'success': False, 'message': '网络已经是激活状态'}), 400
    
    try:
        network.is_active = True
        db.session.commit()
        return jsonify({'success': True, 'message': '网络已激活'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'网络激活失败: {str(e)}'}), 500

@api_bp.route('/networks/<int:network_id>/deactivate', methods=['POST'])
@login_required
def deactivate_network(network_id):
    """停用网络"""
    network = Network.query.get_or_404(network_id)
    
    # 检查权限
    if network.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    if not network.is_active:
        return jsonify({'success': False, 'message': '网络已经是停用状态'}), 400
    
    if not network.can_delete():
        return jsonify({'success': False, 'message': '网络正在使用中，无法停用'}), 400
    
    try:
        network.is_active = False
        db.session.commit()
        return jsonify({'success': True, 'message': '网络已停用'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'网络停用失败: {str(e)}'}), 500

# 镜像管理API
@api_bp.route('/images', methods=['GET'])
@login_required
def list_images():
    """获取镜像列表"""
    engine_name = request.args.get('engine')
    
    try:
        if engine_name:
            images = engine_manager.list_images(engine_name)
            return jsonify({
                'success': True,
                'data': {
                    engine_name: [img.__dict__ for img in images]
                }
            })
        else:
            all_images = engine_manager.list_all_images()
            # 转换ImageInfo对象为字典
            for engine, images in all_images.items():
                all_images[engine] = [img.__dict__ for img in images]
            
            return jsonify({
                'success': True,
                'data': all_images
            })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取镜像列表失败: {str(e)}'}), 500

@api_bp.route('/images/pull', methods=['POST'])
@login_required
def pull_image():
    """拉取镜像"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    data = request.get_json()
    image = data.get('image', '').strip()
    tag = data.get('tag', 'latest').strip()
    engine_name = data.get('engine_name')
    
    if not image:
        return jsonify({'success': False, 'message': '镜像名称不能为空'}), 400
    
    try:
        success = engine_manager.pull_image(image, tag, engine_name)
        if success:
            return jsonify({'success': True, 'message': f'镜像 {image}:{tag} 拉取成功'})
        else:
            return jsonify({'success': False, 'message': '镜像拉取失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'镜像拉取失败: {str(e)}'}), 500

@api_bp.route('/images/<image_id>', methods=['DELETE'])
@login_required
def delete_image(image_id):
    """删除镜像"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    engine_name = request.args.get('engine')
    force = request.json.get('force', False) if request.is_json else False
    
    try:
        success = engine_manager.remove_image(image_id, force, engine_name)
        if success:
            return jsonify({'success': True, 'message': '镜像删除成功'})
        else:
            return jsonify({'success': False, 'message': '镜像删除失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'镜像删除失败: {str(e)}'}), 500

# 模板管理API
@api_bp.route('/templates', methods=['GET'])
@login_required
def list_templates():
    """获取模板列表"""
    category = request.args.get('category')
    search = request.args.get('search')
    
    if search:
        templates = Template.search_templates(search, current_user.id)
    elif category:
        templates = Template.get_by_category(category)
        # 过滤用户可见的模板
        templates = [t for t in templates if t.is_public or t.created_by == current_user.id]
    else:
        templates = Template.get_available_templates(current_user.id)
    
    return jsonify({
        'success': True,
        'data': [t.to_dict() for t in templates]
    })

@api_bp.route('/templates/<int:template_id>', methods=['GET'])
@login_required
def get_template(template_id):
    """获取模板详情"""
    template = Template.query.get_or_404(template_id)
    
    # 检查权限
    if not template.is_public and template.created_by != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    return jsonify({
        'success': True,
        'data': template.to_dict(include_content=True)
    })

@api_bp.route('/templates/<int:template_id>', methods=['DELETE'])
@login_required
def delete_template(template_id):
    """删除模板"""
    template = Template.query.get_or_404(template_id)
    
    # 检查权限
    if template.created_by != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    try:
        db.session.delete(template)
        db.session.commit()
        return jsonify({'success': True, 'message': '模板删除成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'模板删除失败: {str(e)}'}), 500

@api_bp.route('/templates/batch/delete', methods=['POST'])
@login_required
def batch_delete_templates():
    """批量删除模板"""
    data = request.get_json()
    template_ids = data.get('template_ids', [])
    
    if not template_ids:
        return jsonify({'success': False, 'message': '未选择模板'}), 400
    
    results = []
    success_count = 0
    
    for template_id in template_ids:
        try:
            template = Template.query.get(template_id)
            if not template:
                results.append({'id': template_id, 'success': False, 'message': '模板不存在'})
                continue
            
            # 检查权限
            if template.created_by != current_user.id and not current_user.is_admin:
                results.append({'id': template_id, 'success': False, 'message': '权限不足'})
                continue
            
            # 删除模板
            db.session.delete(template)
            success_count += 1
            results.append({'id': template_id, 'success': True, 'message': '模板删除成功'})
            
        except Exception as e:
            results.append({'id': template_id, 'success': False, 'message': f'模板删除失败: {str(e)}'})
    
    if success_count > 0:
        db.session.commit()
    else:
        db.session.rollback()
    
    return jsonify({
        'success': success_count > 0,
        'message': f'批量删除完成，成功 {success_count}/{len(template_ids)} 个模板',
        'data': {'results': results, 'success_count': success_count, 'failed_count': len(template_ids) - success_count}
    })

# 引擎管理API
@api_bp.route('/engines', methods=['GET'])
@login_required
def list_engines():
    """获取引擎列表"""
    engines = engine_manager.list_engines()
    return jsonify({
        'success': True,
        'data': engines
    })

@api_bp.route('/engines/health', methods=['GET'])
@login_required
def check_engines_health():
    """检查引擎健康状态"""
    health_status = engine_manager.health_check()
    return jsonify({
        'success': True,
        'data': health_status
    })

# 文件管理API
@api_bp.route('/files', methods=['GET'])
@login_required
def list_files():
    """获取文件列表"""
    path = request.args.get('path', '/')
    
    try:
        # 获取当前用户的容器
        containers = Container.query.filter_by(user_id=current_user.id).all()
        if not containers:
            return jsonify({'success': False, 'message': '没有可用的容器'}), 404
        
        # 使用第一个可用的容器进行文件操作
        container = containers[0]
        if not container.is_running():
            return jsonify({'success': False, 'message': '容器未运行'}), 400
        
        # 列出目录内容
        command = f"ls -la '{path}'"
        result = engine_manager.exec_command(
            container.container_id, 
            command, 
            container.engine_name
        )
        
        if result['exit_code'] == 0:
            files = []
            lines = result['output'].strip().split('\n')[1:]  # 跳过第一行总计
            
            for line in lines:
                if not line.strip():
                    continue
                    
                parts = line.split()
                if len(parts) >= 9:
                    permissions = parts[0]
                    size = parts[4] if parts[4].isdigit() else '0'
                    modified = ' '.join(parts[5:8])
                    name = ' '.join(parts[8:])
                    
                    # 跳过.和..目录
                    if name in ['.', '..']:
                        continue
                    
                    file_type = 'directory' if permissions.startswith('d') else 'file'
                    file_path = os.path.join(path, name)
                    
                    files.append({
                        'name': name,
                        'type': file_type,
                        'path': file_path,
                        'size': int(size) if size.isdigit() else 0,
                        'modified': modified,
                        'permissions': permissions
                    })
            
            return jsonify({
                'success': True,
                'data': files,
                'current_path': path
            })
        else:
            return jsonify({'success': False, 'message': f'无法访问路径: {path}'}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取文件列表失败: {str(e)}'}), 500

@api_bp.route('/files/content', methods=['GET'])
@login_required
def get_file_content():
    """获取文件内容"""
    path = request.args.get('path')
    if not path:
        return jsonify({'success': False, 'message': '文件路径不能为空'}), 400
    
    try:
        # 获取当前用户的容器
        containers = Container.query.filter_by(user_id=current_user.id).all()
        if not containers:
            return jsonify({'success': False, 'message': '没有可用的容器'}), 404
        
        container = containers[0]
        if not container.is_running():
            return jsonify({'success': False, 'message': '容器未运行'}), 400
        
        # 读取文件内容
        command = f"cat '{path}'"
        result = engine_manager.exec_command(
            container.container_id, 
            command, 
            container.engine_name
        )
        
        if result['exit_code'] == 0:
            return jsonify({
                'success': True,
                'data': result['output']
            })
        else:
            return jsonify({'success': False, 'message': f'无法读取文件: {path}'}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'读取文件失败: {str(e)}'}), 500

@api_bp.route('/files', methods=['POST'])
@login_required
def create_file():
    """创建文件"""
    data = request.get_json()
    path = data.get('path')
    content = data.get('content', '')
    
    if not path:
        return jsonify({'success': False, 'message': '文件路径不能为空'}), 400
    
    try:
        # 获取当前用户的容器
        containers = Container.query.filter_by(user_id=current_user.id).all()
        if not containers:
            return jsonify({'success': False, 'message': '没有可用的容器'}), 404
        
        container = containers[0]
        if not container.is_running():
            return jsonify({'success': False, 'message': '容器未运行'}), 400
        
        # 创建文件
        escaped_content = content.replace("'", "'\"'\"'")
        command = f"echo '{escaped_content}' > '{path}'"
        result = engine_manager.exec_command(
            container.container_id, 
            command, 
            container.engine_name
        )
        
        if result['exit_code'] == 0:
            return jsonify({'success': True, 'message': '文件创建成功'})
        else:
            return jsonify({'success': False, 'message': f'创建文件失败: {result["error"]}'}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'创建文件失败: {str(e)}'}), 500

@api_bp.route('/files', methods=['PUT'])
@login_required
def update_file():
    """更新文件"""
    data = request.get_json()
    path = data.get('path')
    content = data.get('content', '')
    
    if not path:
        return jsonify({'success': False, 'message': '文件路径不能为空'}), 400
    
    try:
        # 获取当前用户的容器
        containers = Container.query.filter_by(user_id=current_user.id).all()
        if not containers:
            return jsonify({'success': False, 'message': '没有可用的容器'}), 404
        
        container = containers[0]
        if not container.is_running():
            return jsonify({'success': False, 'message': '容器未运行'}), 400
        
        # 更新文件内容
        escaped_content = content.replace("'", "'\"'\"'")
        command = f"echo '{escaped_content}' > '{path}'"
        result = engine_manager.exec_command(
            container.container_id, 
            command, 
            container.engine_name
        )
        
        if result['exit_code'] == 0:
            return jsonify({'success': True, 'message': '文件更新成功'})
        else:
            return jsonify({'success': False, 'message': f'更新文件失败: {result["error"]}'}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新文件失败: {str(e)}'}), 500

@api_bp.route('/files', methods=['DELETE'])
@login_required
def delete_file():
    """删除文件"""
    path = request.args.get('path')
    if not path:
        return jsonify({'success': False, 'message': '文件路径不能为空'}), 400
    
    try:
        # 获取当前用户的容器
        containers = Container.query.filter_by(user_id=current_user.id).all()
        if not containers:
            return jsonify({'success': False, 'message': '没有可用的容器'}), 404
        
        container = containers[0]
        if not container.is_running():
            return jsonify({'success': False, 'message': '容器未运行'}), 400
        
        # 删除文件
        command = f"rm -f '{path}'"
        result = engine_manager.exec_command(
            container.container_id, 
            command, 
            container.engine_name
        )
        
        if result['exit_code'] == 0:
            return jsonify({'success': True, 'message': '文件删除成功'})
        else:
            return jsonify({'success': False, 'message': f'删除文件失败: {result["error"]}'}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除文件失败: {str(e)}'}), 500

@api_bp.route('/files/batch/delete', methods=['POST'])
@login_required
def batch_delete_files():
    """批量删除文件"""
    try:
        data = request.get_json()
        paths = data.get('paths', [])
        
        if not paths or not isinstance(paths, list):
            return jsonify({'success': False, 'message': '路径列表不能为空'}), 400
        
        # 安全检查
        for path in paths:
            if '..' in path or path.startswith('/'):
                return jsonify({'success': False, 'message': '无效的路径: ' + path}), 400
        
        # 获取当前用户的容器
        containers = Container.query.filter_by(user_id=current_user.id).all()
        if not containers:
            return jsonify({'success': False, 'message': '没有可用的容器'}), 404
        
        container = containers[0]
        if not container.is_running():
            return jsonify({'success': False, 'message': '容器未运行'}), 400
        
        # 执行批量删除命令
        success_count = 0
        errors = []
        
        for path in paths:
            command = f"rm -rf '{path}'"
            result = engine_manager.exec_command(
                container.container_id, 
                command, 
                container.engine_name
            )
            if result['exit_code'] == 0:
                success_count += 1
            else:
                errors.append(f'{path}: {result.get("error", "删除失败")}')
        
        if success_count == len(paths):
            return jsonify({'success': True, 'message': '批量删除成功'})
        else:
            return jsonify({
                'success': False, 
                'message': f'批量删除部分失败: {success_count}/{len(paths)} 成功',
                'details': errors
            }), 400
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'批量删除失败: {str(e)}'}), 500

@api_bp.route('/files/upload', methods=['POST'])
@login_required
def upload_files():
    """上传文件"""
    if 'files' not in request.files:
        return jsonify({'success': False, 'message': '没有选择文件'}), 400
    
    files = request.files.getlist('files')
    path = request.form.get('path', '/')
    
    if not files:
        return jsonify({'success': False, 'message': '没有选择文件'}), 400
    
    try:
        # 获取当前用户的容器
        containers = Container.query.filter_by(user_id=current_user.id).all()
        if not containers:
            return jsonify({'success': False, 'message': '没有可用的容器'}), 404
        
        container = containers[0]
        if not container.is_running():
            return jsonify({'success': False, 'message': '容器未运行'}), 400
        
        uploaded_files = []
        failed_files = []
        
        for file in files:
            if file.filename == '':
                continue
                
            try:
                # 保存文件到临时位置
                temp_path = os.path.join('/tmp', file.filename)
                file.save(temp_path)
                
                # 读取文件内容
                with open(temp_path, 'rb') as f:
                    content = f.read()
                
                # 转换为base64以便传输
                import base64
                encoded_content = base64.b64encode(content).decode('utf-8')
                
                # 在容器中创建文件
                file_path = os.path.join(path, file.filename)
                command = f"echo '{encoded_content}' | base64 -d > '{file_path}'"
                result = engine_manager.exec_command(
                    container.container_id, 
                    command, 
                    container.engine_name
                )
                
                # 清理临时文件
                os.remove(temp_path)
                
                if result['exit_code'] == 0:
                    uploaded_files.append(file.filename)
                else:
                    failed_files.append({'filename': file.filename, 'error': result['error']})
                    
            except Exception as e:
                failed_files.append({'filename': file.filename, 'error': str(e)})
        
        message = f'上传完成，成功 {len(uploaded_files)} 个文件'
        if failed_files:
            message += f'，失败 {len(failed_files)} 个文件'
        
        return jsonify({
            'success': len(uploaded_files) > 0,
            'message': message,
            'data': {
                'uploaded': uploaded_files,
                'failed': failed_files
            }
        })
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'上传文件失败: {str(e)}'}), 500

@api_bp.route('/files/directory', methods=['POST'])
@login_required
def create_directory():
    """创建目录"""
    data = request.get_json()
    path = data.get('path')
    name = data.get('name')
    
    if not path or not name:
        return jsonify({'success': False, 'message': '路径和名称不能为空'}), 400
    
    try:
        # 获取当前用户的容器
        containers = Container.query.filter_by(user_id=current_user.id).all()
        if not containers:
            return jsonify({'success': False, 'message': '没有可用的容器'}), 404
        
        container = containers[0]
        if not container.is_running():
            return jsonify({'success': False, 'message': '容器未运行'}), 400
        
        # 创建目录
        dir_path = os.path.join(path, name)
        command = f"mkdir -p '{dir_path}'"
        result = engine_manager.exec_command(
            container.container_id, 
            command, 
            container.engine_name
        )
        
        if result['exit_code'] == 0:
            return jsonify({'success': True, 'message': '目录创建成功'})
        else:
            return jsonify({'success': False, 'message': f'创建目录失败: {result["error"]}'}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'创建目录失败: {str(e)}'}), 500