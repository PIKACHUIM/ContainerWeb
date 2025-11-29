from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from flask_socketio import emit, join_room, leave_room, disconnect
import os
import json
import threading
import time

from app import socketio, db
from app.models import Container
from app.container_engines.manager import engine_manager

websocket_bp = Blueprint('websocket', __name__)

# 存储活跃的终端会话
active_terminals = {}

@socketio.on('connect')
def handle_connect():
    """WebSocket连接处理"""
    if not current_user.is_authenticated:
        disconnect()
        return False
    
    print(f'User {current_user.username} connected')
    emit('connected', {'message': '连接成功'})

@socketio.on('disconnect')
def handle_disconnect():
    """WebSocket断开连接处理"""
    if current_user.is_authenticated:
        print(f'User {current_user.username} disconnected')
        
        # 清理用户的终端会话
        user_terminals = [k for k in active_terminals.keys() if k.startswith(f"{current_user.id}_")]
        for terminal_id in user_terminals:
            if terminal_id in active_terminals:
                del active_terminals[terminal_id]

@socketio.on('join_terminal')
def handle_join_terminal(data):
    """加入终端会话"""
    if not current_user.is_authenticated:
        disconnect()
        return
    
    container_id = data.get('container_id')
    if not container_id:
        emit('error', {'message': '容器ID不能为空'})
        return
    
    # 检查容器权限
    container = Container.query.get(container_id)
    if not container:
        emit('error', {'message': '容器不存在'})
        return
    
    if container.user_id != current_user.id and not current_user.is_admin:
        emit('error', {'message': '权限不足'})
        return
    
    if not container.is_running():
        emit('error', {'message': '容器未运行'})
        return
    
    # 创建终端会话ID
    terminal_id = f"{current_user.id}_{container_id}"
    
    # 加入房间
    join_room(terminal_id)
    
    # 初始化终端会话
    if terminal_id not in active_terminals:
        active_terminals[terminal_id] = {
            'container': container,
            'users': set(),
            'history': []
        }
    
    active_terminals[terminal_id]['users'].add(current_user.id)
    
    emit('terminal_ready', {
        'terminal_id': terminal_id,
        'container_name': container.actions,
        'message': f'已连接到容器 {container.actions} 的终端'
    })
    
    # 发送历史记录
    if active_terminals[terminal_id]['history']:
        emit('terminal_output', {
            'output': '\n'.join(active_terminals[terminal_id]['history'][-50:])  # 最近50行
        })

@socketio.on('leave_terminal')
def handle_leave_terminal(data):
    """离开终端会话"""
    if not current_user.is_authenticated:
        return
    
    terminal_id = data.get('terminal_id')
    if not terminal_id:
        return
    
    leave_room(terminal_id)
    
    if terminal_id in active_terminals:
        active_terminals[terminal_id]['users'].discard(current_user.id)
        
        # 如果没有用户了，清理会话
        if not active_terminals[terminal_id]['users']:
            del active_terminals[terminal_id]

@socketio.on('terminal_input')
def handle_terminal_input(data):
    """处理终端输入"""
    if not current_user.is_authenticated:
        disconnect()
        return
    
    terminal_id = data.get('terminal_id')
    command = data.get('input', '').strip()
    
    if not terminal_id or terminal_id not in active_terminals:
        emit('error', {'message': '终端会话不存在'})
        return
    
    if not command:
        return
    
    container = active_terminals[terminal_id]['container']
    
    try:
        # 执行命令
        result = engine_manager.exec_command(
            container.container_id, 
            command, 
            container.engine_name
        )
        
        # 格式化输出
        output_lines = []
        output_lines.append(f"$ {command}")
        
        if result['output']:
            output_lines.extend(result['output'].split('\n'))
        
        if result['exit_code'] != 0:
            output_lines.append(f"Exit code: {result['exit_code']}")
        
        output = '\n'.join(output_lines)
        
        # 保存到历史记录
        active_terminals[terminal_id]['history'].extend(output_lines)
        
        # 限制历史记录长度
        if len(active_terminals[terminal_id]['history']) > 1000:
            active_terminals[terminal_id]['history'] = active_terminals[terminal_id]['history'][-500:]
        
        # 发送输出到房间内所有用户
        socketio.emit('terminal_output', {
            'output': output,
            'exit_code': result['exit_code']
        }, room=terminal_id)
        
    except Exception as e:
        error_msg = f"命令执行失败: {str(e)}"
        active_terminals[terminal_id]['history'].append(error_msg)
        
        socketio.emit('terminal_output', {
            'output': error_msg,
            'exit_code': -1,
            'error': True
        }, room=terminal_id)

@socketio.on('container_logs')
def handle_container_logs(data):
    """获取容器日志"""
    if not current_user.is_authenticated:
        disconnect()
        return
    
    container_id = data.get('container_id')
    tail = data.get('tail', 100)
    
    if not container_id:
        emit('error', {'message': '容器ID不能为空'})
        return
    
    # 检查容器权限
    container = Container.query.get(container_id)
    if not container:
        emit('error', {'message': '容器不存在'})
        return
    
    if container.user_id != current_user.id and not current_user.is_admin:
        emit('error', {'message': '权限不足'})
        return
    
    try:
        logs = engine_manager.get_container_logs(
            container.container_id, 
            tail, 
            container.engine_name
        )
        
        emit('container_logs_data', {
            'container_id': container_id,
            'logs': logs
        })
        
    except Exception as e:
        emit('error', {'message': f'获取日志失败: {str(e)}'})

@socketio.on('monitor_container')
def handle_monitor_container(data):
    """监控容器状态"""
    if not current_user.is_authenticated:
        disconnect()
        return
    
    container_id = data.get('container_id')
    action = data.get('action', 'start')  # start, stop
    
    if not container_id:
        emit('error', {'message': '容器ID不能为空'})
        return
    
    # 检查容器权限
    container = Container.query.get(container_id)
    if not container:
        emit('error', {'message': '容器不存在'})
        return
    
    if container.user_id != current_user.id and not current_user.is_admin:
        emit('error', {'message': '权限不足'})
        return
    
    room_name = f"monitor_{container_id}"
    
    if action == 'start':
        join_room(room_name)
        
        # 启动监控线程
        def monitor_thread():
            while room_name in [room for room in socketio.server.manager.rooms.get('/', {}).keys()]:
                try:
                    # 获取容器实时信息
                    engine_container = engine_manager.get_container(
                        container.container_id, 
                        container.engine_name
                    )
                    
                    if engine_container:
                        # 更新数据库中的容器状态
                        container.update_status(engine_container.status)
                        container.ip_address = engine_container.ip_address
                        container.update_stats(engine_container.cpu_usage, engine_container.memory_usage)
                        db.session.commit()
                        
                        # 发送实时数据
                        socketio.emit('container_stats', {
                            'container_id': container_id,
                            'status': engine_container.status,
                            'cpu_usage': engine_container.cpu_usage,
                            'memory_usage': engine_container.memory_usage,
                            'ip_address': engine_container.ip_address,
                            'timestamp': time.time()
                        }, room=room_name)
                    
                    time.sleep(5)  # 每5秒更新一次
                    
                except Exception as e:
                    socketio.emit('error', {
                        'message': f'监控失败: {str(e)}'
                    }, room=room_name)
                    break
        
        # 启动监控线程
        thread = threading.Thread(target=monitor_thread)
        thread.daemon = True
        thread.start()
        
        emit('monitor_started', {'container_id': container_id})
        
    elif action == 'stop':
        leave_room(room_name)
        emit('monitor_stopped', {'container_id': container_id})

@socketio.on('file_browser')
def handle_file_browser(data):
    """文件浏览器"""
    if not current_user.is_authenticated:
        disconnect()
        return
    
    container_id = data.get('container_id')
    path = data.get('path', '/')
    action = data.get('action', 'list')  # list, read, write, delete
    
    if not container_id:
        emit('error', {'message': '容器ID不能为空'})
        return
    
    # 检查容器权限
    container = Container.query.get(container_id)
    if not container:
        emit('error', {'message': '容器不存在'})
        return
    
    if container.user_id != current_user.id and not current_user.is_admin:
        emit('error', {'message': '权限不足'})
        return
    
    if not container.is_running():
        emit('error', {'message': '容器未运行'})
        return
    
    try:
        if action == 'list':
            # 列出目录内容
            command = f"ls -la '{path}'"
            result = engine_manager.exec_command(
                container.container_id, 
                command, 
                container.engine_name
            )
            
            if result['exit_code'] == 0:
                emit('file_list', {
                    'path': path,
                    'content': result['output']
                })
            else:
                emit('error', {'message': f'无法访问路径: {path}'})
                
        elif action == 'read':
            # 读取文件内容
            file_path = data.get('file_path')
            if not file_path:
                emit('error', {'message': '文件路径不能为空'})
                return
            
            command = f"cat '{file_path}'"
            result = engine_manager.exec_command(
                container.container_id, 
                command, 
                container.engine_name
            )
            
            if result['exit_code'] == 0:
                emit('file_content', {
                    'file_path': file_path,
                    'content': result['output']
                })
            else:
                emit('error', {'message': f'无法读取文件: {file_path}'})
                
        elif action == 'write':
            # 写入文件内容
            file_path = data.get('file_path')
            content = data.get('content', '')
            
            if not file_path:
                emit('error', {'message': '文件路径不能为空'})
                return
            
            # 使用echo写入文件（简单实现）
            escaped_content = content.replace("'", "'\"'\"'")
            command = f"echo '{escaped_content}' > '{file_path}'"
            result = engine_manager.exec_command(
                container.container_id, 
                command, 
                container.engine_name
            )
            
            if result['exit_code'] == 0:
                emit('file_saved', {'file_path': file_path})
            else:
                emit('error', {'message': f'无法保存文件: {file_path}'})
                
        elif action == 'delete':
            # 删除文件
            file_path = data.get('file_path')
            if not file_path:
                emit('error', {'message': '文件路径不能为空'})
                return
            
            command = f"rm -f '{file_path}'"
            result = engine_manager.exec_command(
                container.container_id, 
                command, 
                container.engine_name
            )
            
            if result['exit_code'] == 0:
                emit('file_deleted', {'file_path': file_path})
            else:
                emit('error', {'message': f'无法删除文件: {file_path}'})
                
    except Exception as e:
        emit('error', {'message': f'文件操作失败: {str(e)}'})

@socketio.on('system_notification')
def handle_system_notification(data):
    """系统通知"""
    if not current_user.is_authenticated or not current_user.is_admin:
        return
    
    message = data.get('message', '')
    notification_type = data.get('type', 'info')  # info, warning, error
    
    if not message:
        return
    
    # 广播给所有连接的用户
    socketio.emit('notification', {
        'message': message,
        'type': notification_type,
        'timestamp': time.time(),
        'from_admin': True
    }, broadcast=True)

# REST API endpoints for WebSocket management
@websocket_bp.route('/api/terminals/active', methods=['GET'])
@login_required
def get_active_terminals():
    """获取活跃终端列表"""
    user_terminals = []
    
    for terminal_id, session in active_terminals.items():
        if current_user.id in session['users'] or current_user.is_admin:
            user_terminals.append({
                'terminal_id': terminal_id,
                'container_name': session['container'].actions,
                'container_id': session['container'].id,
                'user_count': len(session['users'])
            })
    
    return jsonify({
        'success': True,
        'data': user_terminals
    })

@websocket_bp.route('/api/terminals/<terminal_id>/history', methods=['GET'])
@login_required
def get_terminal_history(terminal_id):
    """获取终端历史记录"""
    if terminal_id not in active_terminals:
        return jsonify({'success': False, 'message': '终端会话不存在'}), 404
    
    session = active_terminals[terminal_id]
    
    # 检查权限
    if current_user.id not in session['users'] and not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    return jsonify({
        'success': True,
        'data': {
            'history': session['history'][-100:],  # 最近100行
            'container_name': session['container'].actions
        }
    })