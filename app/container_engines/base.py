from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class ContainerConfig:
    """容器配置类"""
    name: str
    image: str
    ports: Dict[str, str] = None  # {"80/tcp": "8080"}
    volumes: Dict[str, str] = None  # {"/host/path": "/container/path"}
    environment: Dict[str, str] = None
    network: str = None
    cpu_limit: float = None
    memory_limit: str = None
    privileged: bool = False
    devices: List[str] = None
    command: str = None
    working_dir: str = None
    user: str = None
    restart_policy: str = "no"

@dataclass
class ContainerInfo:
    """容器信息类"""
    id: str
    name: str
    image: str
    status: str
    created: str
    ports: Dict[str, str] = None
    volumes: Dict[str, str] = None
    network: str = None
    cpu_usage: float = 0.0
    memory_usage: str = "0MB"
    ip_address: str = None

@dataclass
class ImageInfo:
    """镜像信息类"""
    id: str
    repository: str
    tag: str
    size: str
    created: str

class ContainerEngine(ABC):
    """容器引擎抽象基类"""
    
    def __init__(self, host: str = None, **kwargs):
        self.host = host
        self.client = None
        self._initialize_client(**kwargs)
    
    @abstractmethod
    def _initialize_client(self, **kwargs):
        """初始化客户端连接"""
        pass
    
    @abstractmethod
    def ping(self) -> bool:
        """检查引擎连接状态"""
        pass
    
    # 容器管理方法
    @abstractmethod
    def create_container(self, config: ContainerConfig) -> str:
        """创建容器，返回容器ID"""
        pass
    
    @abstractmethod
    def start_container(self, container_id: str) -> bool:
        """启动容器"""
        pass
    
    @abstractmethod
    def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """停止容器"""
        pass
    
    @abstractmethod
    def restart_container(self, container_id: str, timeout: int = 10) -> bool:
        """重启容器"""
        pass
    
    @abstractmethod
    def remove_container(self, container_id: str, force: bool = False) -> bool:
        """删除容器"""
        pass
    
    @abstractmethod
    def get_container(self, container_id: str) -> Optional[ContainerInfo]:
        """获取容器信息"""
        pass
    
    @abstractmethod
    def list_containers(self, all: bool = False) -> List[ContainerInfo]:
        """列出容器"""
        pass
    
    @abstractmethod
    def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        """获取容器日志"""
        pass
    
    @abstractmethod
    def exec_command(self, container_id: str, command: str) -> Dict[str, Any]:
        """在容器中执行命令"""
        pass
    
    # 镜像管理方法
    @abstractmethod
    def pull_image(self, image: str, tag: str = "latest") -> bool:
        """拉取镜像"""
        pass
    
    @abstractmethod
    def list_images(self) -> List[ImageInfo]:
        """列出镜像"""
        pass
    
    @abstractmethod
    def remove_image(self, image_id: str, force: bool = False) -> bool:
        """删除镜像"""
        pass
    
    @abstractmethod
    def build_image(self, dockerfile_path: str, tag: str, build_args: Dict[str, str] = None) -> bool:
        """构建镜像"""
        pass
    
    @abstractmethod
    def commit_container(self, container_id: str, repository: str, tag: str = "latest") -> str:
        """将容器保存为镜像"""
        pass
    
    # 网络管理方法
    @abstractmethod
    def create_network(self, name: str, driver: str = "bridge", subnet: str = None) -> str:
        """创建网络"""
        pass
    
    @abstractmethod
    def list_networks(self) -> List[Dict[str, Any]]:
        """列出网络"""
        pass
    
    @abstractmethod
    def remove_network(self, network_id: str) -> bool:
        """删除网络"""
        pass
    
    @abstractmethod
    def connect_container_to_network(self, container_id: str, network_id: str) -> bool:
        """将容器连接到网络"""
        pass
    
    @abstractmethod
    def disconnect_container_from_network(self, container_id: str, network_id: str) -> bool:
        """将容器从网络断开"""
        pass
    
    # 系统信息方法
    @abstractmethod
    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        pass
    
    @abstractmethod
    def get_version(self) -> Dict[str, Any]:
        """获取引擎版本信息"""
        pass