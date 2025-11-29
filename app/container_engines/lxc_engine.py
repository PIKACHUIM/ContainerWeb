import subprocess
import json
import os
import requests
from typing import Dict, List, Optional, Any
import logging

from .base import ContainerEngine, ContainerConfig, ContainerInfo, ImageInfo

logger = logging.getLogger(__name__)

class LXCEngine(ContainerEngine):
    """LXC容器引擎实现"""
    
    def __init__(self, host: str = None, mode: str = "local", **kwargs):
        """
        初始化LXC引擎
        mode: "local" 使用本地命令行, "remote" 使用远程API
        """
        self.mode = mode
        super().__init__(host, **kwargs)
    
    def _initialize_client(self, **kwargs):
        """初始化LXC客户端"""
        try:
            if self.mode == "local":
                # 检查LXC是否安装
                result = subprocess.run(['lxc', '--version'], capture_output=True, text=True)
                if result.returncode != 0:
                    raise Exception("LXC not installed or not accessible")
                logger.info("LXC local client initialized")
            else:
                # 远程API模式
                if not self.host:
                    self.host = "http://localhost:8443"
                elif not self.host.startswith('http'):
                    self.host = f"https://{self.host}:8443"
                
                self.session = requests.Session()
                # 这里应该配置证书和认证
                self.session.verify = False  # 在生产环境中应该使用正确的证书
                logger.info(f"LXC remote client initialized with host: {self.host}")
        except Exception as e:
            logger.error(f"Failed to initialize LXC client: {e}")
            raise
    
    def ping(self) -> bool:
        """检查LXC连接状态"""
        try:
            if self.mode == "local":
                result = subprocess.run(['lxc', 'list', '--format=json'], 
                                      capture_output=True, text=True, timeout=5)
                return result.returncode == 0
            else:
                response = self.session.get(f"{self.host}/1.0", timeout=5)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"LXC ping failed: {e}")
            return False
    
    def create_container(self, config: ContainerConfig) -> str:
        """创建LXC容器"""
        try:
            if self.mode == "local":
                return self._create_container_local(config)
            else:
                return self._create_container_remote(config)
        except Exception as e:
            logger.error(f"Failed to create LXC container: {e}")
            raise
    
    def _create_container_local(self, config: ContainerConfig) -> str:
        """本地创建LXC容器"""
        # 创建容器
        cmd = ['lxc', 'launch', config.image, config.name]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Failed to create container: {result.stderr}")
        
        # 配置容器
        if config.cpu_limit:
            subprocess.run(['lxc', 'config', 'set', config.name, 
                          f'limits.cpu={config.cpu_limit}'])
        
        if config.memory_limit:
            subprocess.run(['lxc', 'config', 'set', config.name, 
                          f'limits.memory={config.memory_limit}'])
        
        # 设备映射
        if config.devices:
            for device in config.devices:
                subprocess.run(['lxc', 'config', 'device', 'add', config.name, 
                              device, 'unix-char', f'path={device}'])
        
        # 环境变量
        if config.environment:
            for key, value in config.environment.items():
                subprocess.run(['lxc', 'config', 'set', config.name, 
                              f'environment.{key}={value}'])
        
        # 卷挂载
        if config.volumes:
            for host_path, container_path in config.volumes.items():
                device_name = f"mount_{hash(container_path) % 1000}"
                subprocess.run(['lxc', 'config', 'device', 'add', config.name,
                              device_name, 'disk', f'source={host_path}',
                              f'path={container_path}'])
        
        # 网络配置
        if config.network:
            subprocess.run(['lxc', 'network', 'attach', config.network, config.name])
        
        logger.info(f"LXC container created: {config.name}")
        return config.name
    
    def _create_container_remote(self, config: ContainerConfig) -> str:
        """远程创建LXC容器"""
        container_config = {
            "name": config.name,
            "source": {
                "type": "image",
                "alias": config.image
            },
            "config": {},
            "devices": {}
        }
        
        # 资源限制
        if config.cpu_limit:
            container_config["config"]["limits.cpu"] = str(config.cpu_limit)
        if config.memory_limit:
            container_config["config"]["limits.memory"] = config.memory_limit
        
        # 环境变量
        if config.environment:
            for key, value in config.environment.items():
                container_config["config"][f"environment.{key}"] = value
        
        # 卷挂载
        if config.volumes:
            for host_path, container_path in config.volumes.items():
                device_name = f"mount_{hash(container_path) % 1000}"
                container_config["devices"][device_name] = {
                    "type": "disk",
                    "source": host_path,
                    "path": container_path
                }
        
        response = self.session.post(f"{self.host}/1.0/containers", json=container_config)
        if response.status_code == 202:
            logger.info(f"LXC container created: {config.name}")
            return config.name
        else:
            raise Exception(f"Failed to create container: {response.message}")
    
    def start_container(self, container_id: str) -> bool:
        """启动容器"""
        try:
            if self.mode == "local":
                result = subprocess.run(['lxc', 'start', container_id], 
                                      capture_output=True, text=True)
                success = result.returncode == 0
            else:
                response = self.session.put(f"{self.host}/1.0/containers/{container_id}/state",
                                          json={"action": "start"})
                success = response.status_code == 202
            
            if success:
                logger.info(f"LXC container started: {container_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to start LXC container {container_id}: {e}")
            return False
    
    def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """停止容器"""
        try:
            if self.mode == "local":
                result = subprocess.run(['lxc', 'stop', container_id, '--timeout', str(timeout)], 
                                      capture_output=True, text=True)
                success = result.returncode == 0
            else:
                response = self.session.put(f"{self.host}/1.0/containers/{container_id}/state",
                                          json={"action": "stop", "timeout": timeout})
                success = response.status_code == 202
            
            if success:
                logger.info(f"LXC container stopped: {container_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to stop LXC container {container_id}: {e}")
            return False
    
    def restart_container(self, container_id: str, timeout: int = 10) -> bool:
        """重启容器"""
        try:
            if self.mode == "local":
                result = subprocess.run(['lxc', 'restart', container_id, '--timeout', str(timeout)], 
                                      capture_output=True, text=True)
                success = result.returncode == 0
            else:
                response = self.session.put(f"{self.host}/1.0/containers/{container_id}/state",
                                          json={"action": "restart", "timeout": timeout})
                success = response.status_code == 202
            
            if success:
                logger.info(f"LXC container restarted: {container_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to restart LXC container {container_id}: {e}")
            return False
    
    def remove_container(self, container_id: str, force: bool = False) -> bool:
        """删除容器"""
        try:
            if self.mode == "local":
                cmd = ['lxc', 'delete', container_id]
                if force:
                    cmd.append('--force')
                result = subprocess.run(cmd, capture_output=True, text=True)
                success = result.returncode == 0
            else:
                response = self.session.delete(f"{self.host}/1.0/containers/{container_id}")
                success = response.status_code == 202
            
            if success:
                logger.info(f"LXC container removed: {container_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to remove LXC container {container_id}: {e}")
            return False
    
    def get_container(self, container_id: str) -> Optional[ContainerInfo]:
        """获取容器信息"""
        try:
            if self.mode == "local":
                result = subprocess.run(['lxc', 'list', container_id, '--format=json'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    containers = json.loads(result.stdout)
                    if containers:
                        return self._lxc_data_to_container_info(containers[0])
            else:
                response = self.session.get(f"{self.host}/1.0/containers/{container_id}")
                if response.status_code == 200:
                    data = response.json()
                    return self._lxc_data_to_container_info(data["metadata"])
            return None
        except Exception as e:
            logger.error(f"Failed to get LXC container {container_id}: {e}")
            return None
    
    def list_containers(self, all: bool = False) -> List[ContainerInfo]:
        """列出容器"""
        try:
            if self.mode == "local":
                result = subprocess.run(['lxc', 'list', '--format=json'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    containers = json.loads(result.stdout)
                    return [self._lxc_data_to_container_info(container) for container in containers]
            else:
                response = self.session.get(f"{self.host}/1.0/containers")
                if response.status_code == 200:
                    container_names = response.json()["metadata"]
                    containers = []
                    for name in container_names:
                        container_name = name.split('/')[-1]
                        container_info = self.get_container(container_name)
                        if container_info:
                            containers.append(container_info)
                    return containers
            return []
        except Exception as e:
            logger.error(f"Failed to list LXC containers: {e}")
            return []
    
    def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        """获取容器日志"""
        try:
            if self.mode == "local":
                # LXC没有直接的日志命令，可以查看系统日志
                result = subprocess.run(['journalctl', '-u', f'lxc@{container_id}', 
                                       '--lines', str(tail)], 
                                      capture_output=True, text=True)
                return result.stdout if result.returncode == 0 else ""
            else:
                # 远程API获取日志
                response = self.session.get(f"{self.host}/1.0/containers/{container_id}/logs")
                return response.message if response.status_code == 200 else ""
        except Exception as e:
            logger.error(f"Failed to get logs for LXC container {container_id}: {e}")
            return ""
    
    def exec_command(self, container_id: str, command: str) -> Dict[str, Any]:
        """在容器中执行命令"""
        try:
            if self.mode == "local":
                cmd = ['lxc', 'exec', container_id, '--'] + command.split()
                result = subprocess.run(cmd, capture_output=True, text=True)
                return {
                    'exit_code': result.returncode,
                    'output': result.stdout + result.stderr
                }
            else:
                exec_config = {
                    "command": command.split(),
                    "wait-for-websocket": False,
                    "interactive": False
                }
                response = self.session.post(f"{self.host}/1.0/containers/{container_id}/exec",
                                           json=exec_config)
                if response.status_code == 202:
                    return {'exit_code': 0, 'output': 'Command executed'}
                else:
                    return {'exit_code': -1, 'output': 'Failed to execute command'}
        except Exception as e:
            logger.error(f"Failed to exec command in LXC container {container_id}: {e}")
            return {'exit_code': -1, 'output': str(e)}
    
    def pull_image(self, image: str, tag: str = "latest") -> bool:
        """拉取镜像（LXC中称为image）"""
        try:
            if self.mode == "local":
                full_image = f"{image}/{tag}" if tag != "latest" else image
                result = subprocess.run(['lxc', 'image', 'copy', f'images:{full_image}', 'local:'],
                                      capture_output=True, text=True)
                success = result.returncode == 0
            else:
                # 远程API拉取镜像
                image_config = {
                    "source": {
                        "type": "image",
                        "mode": "pull",
                        "server": "https://images.linuxcontainers.org",
                        "protocol": "simplestreams",
                        "alias": f"{image}/{tag}" if tag != "latest" else image
                    }
                }
                response = self.session.post(f"{self.host}/1.0/images", json=image_config)
                success = response.status_code == 202
            
            if success:
                logger.info(f"LXC image pulled: {image}:{tag}")
            return success
        except Exception as e:
            logger.error(f"Failed to pull LXC image {image}:{tag}: {e}")
            return False
    
    def list_images(self) -> List[ImageInfo]:
        """列出镜像"""
        try:
            if self.mode == "local":
                result = subprocess.run(['lxc', 'image', 'list', '--format=json'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    images = json.loads(result.stdout)
                    return [self._lxc_data_to_image_info(image) for image in images]
            else:
                response = self.session.get(f"{self.host}/1.0/images")
                if response.status_code == 200:
                    image_urls = response.json()["metadata"]
                    images = []
                    for url in image_urls:
                        image_response = self.session.get(f"{self.host}{url}")
                        if image_response.status_code == 200:
                            images.append(self._lxc_data_to_image_info(image_response.json()["metadata"]))
                    return images
            return []
        except Exception as e:
            logger.error(f"Failed to list LXC images: {e}")
            return []
    
    def remove_image(self, image_id: str, force: bool = False) -> bool:
        """删除镜像"""
        try:
            if self.mode == "local":
                result = subprocess.run(['lxc', 'image', 'delete', image_id], 
                                      capture_output=True, text=True)
                success = result.returncode == 0
            else:
                response = self.session.delete(f"{self.host}/1.0/images/{image_id}")
                success = response.status_code == 202
            
            if success:
                logger.info(f"LXC image removed: {image_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to remove LXC image {image_id}: {e}")
            return False
    
    def build_image(self, dockerfile_path: str, tag: str, build_args: Dict[str, str] = None) -> bool:
        """构建镜像（LXC不直接支持Dockerfile）"""
        logger.warning("LXC does not support Dockerfile builds")
        return False
    
    def commit_container(self, container_id: str, repository: str, tag: str = "latest") -> str:
        """将容器保存为镜像"""
        try:
            alias = f"{repository}_{tag}"
            if self.mode == "local":
                result = subprocess.run(['lxc', 'publish', container_id, '--alias', alias], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info(f"LXC container committed to image: {alias}")
                    return alias
            else:
                publish_config = {
                    "aliases": [{"name": alias}]
                }
                response = self.session.post(f"{self.host}/1.0/containers/{container_id}/publish",
                                           json=publish_config)
                if response.status_code == 202:
                    logger.info(f"LXC container committed to image: {alias}")
                    return alias
            raise Exception("Failed to commit container")
        except Exception as e:
            logger.error(f"Failed to commit LXC container {container_id}: {e}")
            raise
    
    def create_network(self, name: str, driver: str = "bridge", subnet: str = None) -> str:
        """创建网络"""
        try:
            if self.mode == "local":
                cmd = ['lxc', 'network', 'create', name]
                if subnet:
                    cmd.extend(['--config', f'ipv4.address={subnet}'])
                result = subprocess.run(cmd, capture_output=True, text=True)
                success = result.returncode == 0
            else:
                network_config = {
                    "name": name,
                    "config": {}
                }
                if subnet:
                    network_config["config"]["ipv4.address"] = subnet
                
                response = self.session.post(f"{self.host}/1.0/networks", json=network_config)
                success = response.status_code == 202
            
            if success:
                logger.info(f"LXC network created: {name}")
                return name
            raise Exception("Failed to create network")
        except Exception as e:
            logger.error(f"Failed to create LXC network {name}: {e}")
            raise
    
    def list_networks(self) -> List[Dict[str, Any]]:
        """列出网络"""
        try:
            if self.mode == "local":
                result = subprocess.run(['lxc', 'network', 'list', '--format=json'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    return json.loads(result.stdout)
            else:
                response = self.session.get(f"{self.host}/1.0/networks")
                if response.status_code == 200:
                    return response.json()["metadata"]
            return []
        except Exception as e:
            logger.error(f"Failed to list LXC networks: {e}")
            return []
    
    def remove_network(self, network_id: str) -> bool:
        """删除网络"""
        try:
            if self.mode == "local":
                result = subprocess.run(['lxc', 'network', 'delete', network_id], 
                                      capture_output=True, text=True)
                success = result.returncode == 0
            else:
                response = self.session.delete(f"{self.host}/1.0/networks/{network_id}")
                success = response.status_code == 202
            
            if success:
                logger.info(f"LXC network removed: {network_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to remove LXC network {network_id}: {e}")
            return False
    
    def connect_container_to_network(self, container_id: str, network_id: str) -> bool:
        """将容器连接到网络"""
        try:
            if self.mode == "local":
                result = subprocess.run(['lxc', 'network', 'attach', network_id, container_id], 
                                      capture_output=True, text=True)
                success = result.returncode == 0
            else:
                # LXC远程API的网络连接需要修改容器配置
                success = False  # 需要具体实现
            
            if success:
                logger.info(f"LXC container {container_id} connected to network {network_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to connect LXC container {container_id} to network {network_id}: {e}")
            return False
    
    def disconnect_container_from_network(self, container_id: str, network_id: str) -> bool:
        """将容器从网络断开"""
        try:
            if self.mode == "local":
                result = subprocess.run(['lxc', 'network', 'detach', network_id, container_id], 
                                      capture_output=True, text=True)
                success = result.returncode == 0
            else:
                # LXC远程API的网络断开需要修改容器配置
                success = False  # 需要具体实现
            
            if success:
                logger.info(f"LXC container {container_id} disconnected from network {network_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to disconnect LXC container {container_id} from network {network_id}: {e}")
            return False
    
    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        try:
            if self.mode == "local":
                result = subprocess.run(['lxc', 'info'], capture_output=True, text=True)
                # 解析输出为字典格式
                info = {}
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if ':' in line:
                            key, value = line.split(':', 1)
                            info[key.strip()] = value.strip()
                return info
            else:
                response = self.session.get(f"{self.host}/1.0")
                if response.status_code == 200:
                    return response.json()["metadata"]
            return {}
        except Exception as e:
            logger.error(f"Failed to get LXC system info: {e}")
            return {}
    
    def get_version(self) -> Dict[str, Any]:
        """获取LXC版本信息"""
        try:
            if self.mode == "local":
                result = subprocess.run(['lxc', '--version'], capture_output=True, text=True)
                if result.returncode == 0:
                    return {"version": result.stdout.strip()}
            else:
                response = self.session.get(f"{self.host}/1.0")
                if response.status_code == 200:
                    return response.json()["metadata"]
            return {}
        except Exception as e:
            logger.error(f"Failed to get LXC version: {e}")
            return {}
    
    def _lxc_data_to_container_info(self, data: Dict[str, Any]) -> ContainerInfo:
        """将LXC数据转换为ContainerInfo"""
        try:
            return ContainerInfo(
                id=data.get('name', ''),
                name=data.get('name', ''),
                image=data.get('config', {}).get('image.description', 'unknown'),
                status=data.get('status', 'unknown'),
                created=data.get('created_at', 'unknown'),
                network=list(data.get('state', {}).get('network', {}).keys())[0] if data.get('state', {}).get('network') else None,
                ip_address=list(data.get('state', {}).get('network', {}).values())[0].get('addresses', [{}])[0].get('address') if data.get('state', {}).get('network') else None
            )
        except Exception as e:
            logger.error(f"Failed to convert LXC data to container info: {e}")
            return ContainerInfo(
                id=data.get('name', 'unknown'),
                name=data.get('name', 'unknown'),
                image='unknown',
                status=data.get('status', 'unknown'),
                created='unknown'
            )
    
    def _lxc_data_to_image_info(self, data: Dict[str, Any]) -> ImageInfo:
        """将LXC数据转换为ImageInfo"""
        try:
            aliases = data.get('aliases', [])
            alias_name = aliases[0].get('name', 'unknown') if aliases else 'unknown'
            
            return ImageInfo(
                id=data.get('fingerprint', 'unknown')[:12],
                repository=alias_name.split('/')[0] if '/' in alias_name else alias_name,
                tag=alias_name.split('/')[1] if '/' in alias_name else 'latest',
                size=f"{data.get('size', 0) / 1024 / 1024:.1f}MB",
                created=data.get('created_at', 'unknown')
            )
        except Exception as e:
            logger.error(f"Failed to convert LXC data to image info: {e}")
            return ImageInfo(
                id='unknown',
                repository='unknown',
                tag='unknown',
                size='unknown',
                created='unknown'
            )