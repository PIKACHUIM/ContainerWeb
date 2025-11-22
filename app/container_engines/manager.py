from typing import Dict, List, Optional, Any, Type
import logging
from enum import Enum

from .base import ContainerEngine, ContainerConfig, ContainerInfo, ImageInfo
from .docker_engine import DockerEngine
from .podman_engine import PodmanEngine
from .lxc_engine import LXCEngine

logger = logging.getLogger(__name__)

class EngineType(Enum):
    """容器引擎类型枚举"""
    DOCKER = "docker"
    PODMAN = "podman"
    LXC = "lxc"

class ContainerEngineManager:
    """容器引擎管理器 - 实现多态和统一接口"""
    
    def __init__(self):
        self._engines: Dict[str, ContainerEngine] = {}
        self._engine_configs: Dict[str, Dict[str, Any]] = {}
        self._default_engine: Optional[str] = None
        
        # 引擎类型映射
        self._engine_classes: Dict[EngineType, Type[ContainerEngine]] = {
            EngineType.DOCKER: DockerEngine,
            EngineType.PODMAN: PodmanEngine,
            EngineType.LXC: LXCEngine
        }
    
    def add_engine(self, name: str, engine_type: EngineType, host: str = None, **kwargs) -> bool:
        """添加容器引擎"""
        try:
            engine_class = self._engine_classes.get(engine_type)
            if not engine_class:
                raise ValueError(f"Unsupported engine type: {engine_type}")
            
            # 创建引擎实例
            engine = engine_class(host=host, **kwargs)
            
            # 测试连接
            if not engine.ping():
                raise Exception(f"Failed to connect to {engine_type.value} engine at {host}")
            
            self._engines[name] = engine
            self._engine_configs[name] = {
                'type': engine_type,
                'host': host,
                'kwargs': kwargs
            }
            
            # 设置第一个成功添加的引擎为默认引擎
            if self._default_engine is None:
                self._default_engine = name
            
            logger.info(f"Engine '{name}' ({engine_type.value}) added successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add engine '{name}': {e}")
            return False
    
    def remove_engine(self, name: str) -> bool:
        """移除容器引擎"""
        try:
            if name in self._engines:
                del self._engines[name]
                del self._engine_configs[name]
                
                # 如果删除的是默认引擎，重新设置默认引擎
                if self._default_engine == name:
                    self._default_engine = next(iter(self._engines.keys())) if self._engines else None
                
                logger.info(f"Engine '{name}' removed successfully")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to remove engine '{name}': {e}")
            return False
    
    def get_engine(self, name: str = None) -> Optional[ContainerEngine]:
        """获取指定的容器引擎，如果未指定则返回默认引擎"""
        if name is None:
            name = self._default_engine
        return self._engines.get(name)
    
    def list_engines(self) -> List[Dict[str, Any]]:
        """列出所有引擎"""
        engines = []
        for name, config in self._engine_configs.items():
            engine = self._engines[name]
            engines.append({
                'name': name,
                'type': config['type'].value,
                'host': config['host'],
                'is_default': name == self._default_engine,
                'is_connected': engine.ping()
            })
        return engines
    
    def set_default_engine(self, name: str) -> bool:
        """设置默认引擎"""
        if name in self._engines:
            self._default_engine = name
            logger.info(f"Default engine set to '{name}'")
            return True
        return False
    
    def get_default_engine_name(self) -> Optional[str]:
        """获取默认引擎名称"""
        return self._default_engine
    
    # 以下方法提供统一的容器管理接口，使用默认引擎或指定引擎
    
    def create_container(self, config: ContainerConfig, engine_name: str = None) -> Optional[str]:
        """创建容器"""
        engine = self.get_engine(engine_name)
        if engine:
            try:
                return engine.create_container(config)
            except Exception as e:
                logger.error(f"Failed to create container with engine '{engine_name or self._default_engine}': {e}")
        return None
    
    def start_container(self, container_id: str, engine_name: str = None) -> bool:
        """启动容器"""
        engine = self.get_engine(engine_name)
        if engine:
            return engine.start_container(container_id)
        return False
    
    def stop_container(self, container_id: str, timeout: int = 10, engine_name: str = None) -> bool:
        """停止容器"""
        engine = self.get_engine(engine_name)
        if engine:
            return engine.stop_container(container_id, timeout)
        return False
    
    def restart_container(self, container_id: str, timeout: int = 10, engine_name: str = None) -> bool:
        """重启容器"""
        engine = self.get_engine(engine_name)
        if engine:
            return engine.restart_container(container_id, timeout)
        return False
    
    def remove_container(self, container_id: str, force: bool = False, engine_name: str = None) -> bool:
        """删除容器"""
        engine = self.get_engine(engine_name)
        if engine:
            return engine.remove_container(container_id, force)
        return False
    
    def get_container(self, container_id: str, engine_name: str = None) -> Optional[ContainerInfo]:
        """获取容器信息"""
        engine = self.get_engine(engine_name)
        if engine:
            return engine.get_container(container_id)
        return None
    
    def list_containers(self, all: bool = False, engine_name: str = None) -> List[ContainerInfo]:
        """列出容器"""
        engine = self.get_engine(engine_name)
        if engine:
            return engine.list_containers(all)
        return []
    
    def list_all_containers(self, all: bool = False) -> Dict[str, List[ContainerInfo]]:
        """列出所有引擎的容器"""
        all_containers = {}
        for name, engine in self._engines.items():
            try:
                containers = engine.list_containers(all)
                all_containers[name] = containers
            except Exception as e:
                logger.error(f"Failed to list containers from engine '{name}': {e}")
                all_containers[name] = []
        return all_containers
    
    def get_container_logs(self, container_id: str, tail: int = 100, engine_name: str = None) -> str:
        """获取容器日志"""
        engine = self.get_engine(engine_name)
        if engine:
            return engine.get_container_logs(container_id, tail)
        return ""
    
    def exec_command(self, container_id: str, command: str, engine_name: str = None) -> Dict[str, Any]:
        """在容器中执行命令"""
        engine = self.get_engine(engine_name)
        if engine:
            return engine.exec_command(container_id, command)
        return {'exit_code': -1, 'output': 'Engine not found'}
    
    def pull_image(self, image: str, tag: str = "latest", engine_name: str = None) -> bool:
        """拉取镜像"""
        engine = self.get_engine(engine_name)
        if engine:
            return engine.pull_image(image, tag)
        return False
    
    def list_images(self, engine_name: str = None) -> List[ImageInfo]:
        """列出镜像"""
        engine = self.get_engine(engine_name)
        if engine:
            return engine.list_images()
        return []
    
    def list_all_images(self) -> Dict[str, List[ImageInfo]]:
        """列出所有引擎的镜像"""
        all_images = {}
        for name, engine in self._engines.items():
            try:
                images = engine.list_images()
                all_images[name] = images
            except Exception as e:
                logger.error(f"Failed to list images from engine '{name}': {e}")
                all_images[name] = []
        return all_images
    
    def remove_image(self, image_id: str, force: bool = False, engine_name: str = None) -> bool:
        """删除镜像"""
        engine = self.get_engine(engine_name)
        if engine:
            return engine.remove_image(image_id, force)
        return False
    
    def build_image(self, dockerfile_path: str, tag: str, build_args: Dict[str, str] = None, engine_name: str = None) -> bool:
        """构建镜像"""
        engine = self.get_engine(engine_name)
        if engine:
            return engine.build_image(dockerfile_path, tag, build_args)
        return False
    
    def commit_container(self, container_id: str, repository: str, tag: str = "latest", engine_name: str = None) -> Optional[str]:
        """将容器保存为镜像"""
        engine = self.get_engine(engine_name)
        if engine:
            try:
                return engine.commit_container(container_id, repository, tag)
            except Exception as e:
                logger.error(f"Failed to commit container with engine '{engine_name or self._default_engine}': {e}")
        return None
    
    def create_network(self, name: str, driver: str = "bridge", subnet: str = None, engine_name: str = None) -> Optional[str]:
        """创建网络"""
        engine = self.get_engine(engine_name)
        if engine:
            try:
                return engine.create_network(name, driver, subnet)
            except Exception as e:
                logger.error(f"Failed to create network with engine '{engine_name or self._default_engine}': {e}")
        return None
    
    def list_networks(self, engine_name: str = None) -> List[Dict[str, Any]]:
        """列出网络"""
        engine = self.get_engine(engine_name)
        if engine:
            return engine.list_networks()
        return []
    
    def list_all_networks(self) -> Dict[str, List[Dict[str, Any]]]:
        """列出所有引擎的网络"""
        all_networks = {}
        for name, engine in self._engines.items():
            try:
                networks = engine.list_networks()
                all_networks[name] = networks
            except Exception as e:
                logger.error(f"Failed to list networks from engine '{name}': {e}")
                all_networks[name] = []
        return all_networks
    
    def remove_network(self, network_id: str, engine_name: str = None) -> bool:
        """删除网络"""
        engine = self.get_engine(engine_name)
        if engine:
            return engine.remove_network(network_id)
        return False
    
    def connect_container_to_network(self, container_id: str, network_id: str, engine_name: str = None) -> bool:
        """将容器连接到网络"""
        engine = self.get_engine(engine_name)
        if engine:
            return engine.connect_container_to_network(container_id, network_id)
        return False
    
    def disconnect_container_from_network(self, container_id: str, network_id: str, engine_name: str = None) -> bool:
        """将容器从网络断开"""
        engine = self.get_engine(engine_name)
        if engine:
            return engine.disconnect_container_from_network(container_id, network_id)
        return False
    
    def get_system_info(self, engine_name: str = None) -> Dict[str, Any]:
        """获取系统信息"""
        engine = self.get_engine(engine_name)
        if engine:
            return engine.get_system_info()
        return {}
    
    def get_all_system_info(self) -> Dict[str, Dict[str, Any]]:
        """获取所有引擎的系统信息"""
        all_info = {}
        for name, engine in self._engines.items():
            try:
                info = engine.get_system_info()
                all_info[name] = info
            except Exception as e:
                logger.error(f"Failed to get system info from engine '{name}': {e}")
                all_info[name] = {}
        return all_info
    
    def get_version(self, engine_name: str = None) -> Dict[str, Any]:
        """获取引擎版本信息"""
        engine = self.get_engine(engine_name)
        if engine:
            return engine.get_version()
        return {}
    
    def get_all_versions(self) -> Dict[str, Dict[str, Any]]:
        """获取所有引擎的版本信息"""
        all_versions = {}
        for name, engine in self._engines.items():
            try:
                version = engine.get_version()
                all_versions[name] = version
            except Exception as e:
                logger.error(f"Failed to get version from engine '{name}': {e}")
                all_versions[name] = {}
        return all_versions
    
    def find_container_engine(self, container_id: str) -> Optional[str]:
        """查找容器所在的引擎"""
        for name, engine in self._engines.items():
            try:
                container = engine.get_container(container_id)
                if container:
                    return name
            except Exception:
                continue
        return None
    
    def health_check(self) -> Dict[str, bool]:
        """检查所有引擎的健康状态"""
        health_status = {}
        for name, engine in self._engines.items():
            try:
                health_status[name] = engine.ping()
            except Exception as e:
                logger.error(f"Health check failed for engine '{name}': {e}")
                health_status[name] = False
        return health_status

# 全局引擎管理器实例
engine_manager = ContainerEngineManager()