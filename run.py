#!/usr/bin/env python3
"""
ContainerWeb 启动脚本
"""

import os
import sys
from app import create_app, socketio

def main():
    """主函数"""
    # 设置环境变量
    os.environ.setdefault('FLASK_CONFIG', 'development')
    
    # 创建应用
    app = create_app()
    
    # 获取配置
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_CONFIG', 'development') == 'development'
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                        ContainerWeb                          ║
║                    容器管理平台启动中...                      ║
╠══════════════════════════════════════════════════════════════╣
║ 访问地址: http://{host}:{port}                               ║
║ 环境模式: {'开发模式' if debug else '生产模式'}                ║
║ 默认管理员: admin / admin123                                 ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    try:
        # 启动应用
        socketio.run(
            app,
            host=host,
            port=port,
            debug=debug,
            allow_unsafe_werkzeug=True
        )
    except KeyboardInterrupt:
        print("\n应用已停止")
        sys.exit(0)
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()