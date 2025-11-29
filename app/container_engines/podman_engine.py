import requests
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from .base import ContainerEngine, ContainerConfig, ContainerInfo, ImageInfo

logger = logging.getLogger(__name__)

class PodmanEngine(ContainerEngine):
    """Podman容器引擎实现（通过HTTP API）"""
    
    def _initialize_client(self, **kwargs):
        """初始化Podman HTTP客户端"""
        try:
            # Podman API默认端口
            if not self.host:
                self.host = "http://localhost:8080"
            elif not self.host.startswith('http'):
                self.host = f"http://{self.host}"
            
            self.api_base = f"{self.host}/v1.0.0/libpod"
            self.session = requests.Session()
            self.session.headers.update({'Content-Type': 'application/json'})
            
            logger.info(f"Podman client initialized with host: {self.host}")
        except Exception as e:
            logger.error(f"Failed to initialize Podman client: {e}")
            raise
    
    def ping(self) -> bool:
        """检查Podman连接状态"""
        try:
            response = self.session.get(f"{self.api_base}/system/ping", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Podman ping failed: {e}")
            return False
    
    def create_container(self, config: ContainerConfig) -> str:
        """创建Podman容器"""
        try:
            # 构建容器配置
            container_config = {
                "name": config.name,
                "image": config.image,
                "command": config.command.split() if config.command else None,
                "env": [f"{k}={v}" for k, v in (config.environment or {}).items()],
                "work_dir": config.working_dir,
                "user": config.user,
                "privileged": config.privileged,
                "restart_policy": config.restart_policy
            }
            
            # 端口映射
            if config.ports:
                port_mappings = []
                for container_port, host_port in config.ports.items():
                    port_mappings.append({
                        "container_port": int(container_port.split('/')[0]),
                        "host_port": int(host_port.split(':')[-1]),
                        "protocol": container_port.split('/')[1] if '/' in container_port else "tcp"
                    })
                container_config["portmappings"] = port_mappings
            
            # 卷挂载
            if config.volumes:
                mounts = []
                for host_path, container_path in config.volumes.items():
                    mounts.append({
                        "destination": container_path,
                        "source": host_path,
                        "type": "bind"
                    })
                container_config["mounts"] = mounts
            
            # 资源限制
            if config.cpu_limit or config.memory_limit:
                resources = {}
                if config.cpu_limit:
                    resources["cpu_quota"] = int(config.cpu_limit * 100000)
                    resources["cpu_period"] = 100000
                if config.memory_limit:
                    # 转换内存限制格式
                    memory_bytes = self._parse_memory(config.memory_limit)
                    resources["memory"] = memory_bytes
                container_config["resource_limits"] = resources
            
            # 网络
            if config.network:
                container_config["networks"] = {config.network: {}}
            
            response = self.session.post(
                f"{self.api_base}/containers/create",
                json=container_config
            )
            
            if response.status_code == 201:
                result = response.json()
                container_id = result.get('Id')
                logger.info(f"Podman container created: {container_id}")
                return container_id
            else:
                raise Exception(f"Failed to create container: {response.message}")
                
        except Exception as e:
            logger.error(f"Failed to create Podman container: {e}")
            raise
    
    def start_container(self, container_id: str) -> bool:
        """启动容器"""
        try:
            response = self.session.post(f"{self.api_base}/containers/{container_id}/start")
            success = response.status_code in [200, 204, 304]
            if success:
                logger.info(f"Podman container started: {container_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to start Podman container {container_id}: {e}")
            return False
    
    def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """停止容器"""
        try:
            response = self.session.post(
                f"{self.api_base}/containers/{container_id}/stop",
                params={"t": timeout}
            )
            success = response.status_code in [200, 204, 304]
            if success:
                logger.info(f"Podman container stopped: {container_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to stop Podman container {container_id}: {e}")
            return False
    
    def restart_container(self, container_id: str, timeout: int = 10) -> bool:
        """重启容器"""
        try:
            response = self.session.post(
                f"{self.api_base}/containers/{container_id}/restart",
                params={"t": timeout}
            )
            success = response.status_code in [200, 204]
            if success:
                logger.info(f"Podman container restarted: {container_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to restart Podman container {container_id}: {e}")
            return False
    
    def remove_container(self, container_id: str, force: bool = False) -> bool:
        """删除容器"""
        try:
            params = {"force": force}
            response = self.session.delete(
                f"{self.api_base}/containers/{container_id}",
                params=params
            )
            success = response.status_code in [200, 204]
            if success:
                logger.info(f"Podman container removed: {container_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to remove Podman container {container_id}: {e}")
            return False
    
    def get_container(self, container_id: str) -> Optional[ContainerInfo]:
        """获取容器信息"""
        try:
            response = self.session.get(f"{self.api_base}/containers/{container_id}/json")
            if response.status_code == 200:
                data = response.json()
                return self._data_to_container_info(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get Podman container {container_id}: {e}")
            return None
    
    def list_containers(self, all: bool = False) -> List[ContainerInfo]:
        """列出容器"""
        try:
            params = {"all": all}
            response = self.session.get(f"{self.api_base}/containers/json", params=params)
            if response.status_code == 200:
                containers_data = response.json()
                return [self._data_to_container_info(data) for data in containers_data]
            return []
        except Exception as e:
            logger.error(f"Failed to list Podman containers: {e}")
            return []
    
    def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        """获取容器日志"""
        try:
            params = {"stdout": True, "stderr": True, "tail": tail, "timestamps": True}
            response = self.session.get(
                f"{self.api_base}/containers/{container_id}/logs",
                params=params
            )
            if response.status_code == 200:
                return response.message
            return ""
        except Exception as e:
            logger.error(f"Failed to get logs for Podman container {container_id}: {e}")
            return ""
    
    def exec_command(self, container_id: str, command: str) -> Dict[str, Any]:
        """在容器中执行命令"""
        try:
            # 创建exec实例
            exec_config = {
                "AttachStdout": True,
                "AttachStderr": True,
                "Cmd": command.split()
            }
            
            response = self.session.post(
                f"{self.api_base}/containers/{container_id}/exec",
                json=exec_config
            )
            
            if response.status_code == 201:
                exec_id = response.json().get('Id')
                
                # 启动exec
                start_response = self.session.post(
                    f"{self.api_base}/exec/{exec_id}/start",
                    json={"Detach": False}
                )
                
                if start_response.status_code == 200:
                    return {
                        'exit_code': 0,
                        'output': start_response.message
                    }
            
            return {'exit_code': -1, 'output': 'Failed to execute command'}
        except Exception as e:
            logger.error(f"Failed to exec command in Podman container {container_id}: {e}")
            return {'exit_code': -1, 'output': str(e)}
    
    def pull_image(self, image: str, tag: str = "latest") -> bool:
        """拉取镜像"""
        try:
            full_image = f"{image}:{tag}"
            response = self.session.post(
                f"{self.api_base}/images/pull",
                params={"reference": full_image}
            )
            success = response.status_code == 200
            if success:
                logger.info(f"Podman image pulled: {full_image}")
            return success
        except Exception as e:
            logger.error(f"Failed to pull Podman image {image}:{tag}: {e}")
            return False
    
    def list_images(self) -> List[ImageInfo]:
        """列出镜像"""
        try:
            response = self.session.get(f"{self.api_base}/images/json")
            if response.status_code == 200:
                images_data = response.json()
                return [self._data_to_image_info(data) for data in images_data]
            return []
        except Exception as e:
            logger.error(f"Failed to list Podman images: {e}")
            return []
    
    def remove_image(self, image_id: str, force: bool = False) -> bool:
        """删除镜像"""
        try:
            params = {"force": force}
            response = self.session.delete(
                f"{self.api_base}/images/{image_id}",
                params=params
            )
            success = response.status_code == 200
            if success:
                logger.info(f"Podman image removed: {image_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to remove Podman image {image_id}: {e}")
            return False
    
    def build_image(self, dockerfile_path: str, tag: str, build_args: Dict[str, str] = None) -> bool:
        """构建镜像"""
        try:
            # Podman build API implementation
            # 这里需要根据具体的Podman API文档实现
            logger.warning("Podman build_image not fully implemented")
            return False
        except Exception as e:
            logger.error(f"Failed to build Podman image {tag}: {e}")
            return False
    
    def commit_container(self, container_id: str, repository: str, tag: str = "latest") -> str:
        """将容器保存为镜像"""
        try:
            params = {
                "container": container_id,
                "repo": repository,
                "tag": tag
            }
            response = self.session.post(f"{self.api_base}/commit", params=params)
            if response.status_code == 200:
                result = response.json()
                image_id = result.get('Id')
                logger.info(f"Podman container committed to image: {repository}:{tag}")
                return image_id
            raise Exception(f"Failed to commit container: {response.message}")
        except Exception as e:
            logger.error(f"Failed to commit Podman container {container_id}: {e}")
            raise
    
    def create_network(self, name: str, driver: str = "bridge", subnet: str = None) -> str:
        """创建网络"""
        try:
            network_config = {
                "name": name,
                "driver": driver
            }
            if subnet:
                network_config["subnet"] = subnet
            
            response = self.session.post(
                f"{self.api_base}/networks/create",
                json=network_config
            )
            
            if response.status_code == 200:
                result = response.json()
                network_id = result.get('Id')
                logger.info(f"Podman network created: {name}")
                return network_id
            raise Exception(f"Failed to create network: {response.message}")
        except Exception as e:
            logger.error(f"Failed to create Podman network {name}: {e}")
            raise
    
    def list_networks(self) -> List[Dict[str, Any]]:
        """列出网络"""
        try:
            response = self.session.get(f"{self.api_base}/networks/json")
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            logger.error(f"Failed to list Podman networks: {e}")
            return []
    
    def remove_network(self, network_id: str) -> bool:
        """删除网络"""
        try:
            response = self.session.delete(f"{self.api_base}/networks/{network_id}")
            success = response.status_code == 200
            if success:
                logger.info(f"Podman network removed: {network_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to remove Podman network {network_id}: {e}")
            return False
    
    def connect_container_to_network(self, container_id: str, network_id: str) -> bool:
        """将容器连接到网络"""
        try:
            config = {"Container": container_id}
            response = self.session.post(
                f"{self.api_base}/networks/{network_id}/connect",
                json=config
            )
            success = response.status_code == 200
            if success:
                logger.info(f"Podman container {container_id} connected to network {network_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to connect Podman container {container_id} to network {network_id}: {e}")
            return False
    
    def disconnect_container_from_network(self, container_id: str, network_id: str) -> bool:
        """将容器从网络断开"""
        try:
            config = {"Container": container_id}
            response = self.session.post(
                f"{self.api_base}/networks/{network_id}/disconnect",
                json=config
            )
            success = response.status_code == 200
            if success:
                logger.info(f"Podman container {container_id} disconnected from network {network_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to disconnect Podman container {container_id} from network {network_id}: {e}")
            return False
    
    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        try:
            response = self.session.get(f"{self.api_base}/system/info")
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            logger.error(f"Failed to get Podman system info: {e}")
            return {}
    
    def get_version(self) -> Dict[str, Any]:
        """获取Podman版本信息"""
        try:
            response = self.session.get(f"{self.api_base}/system/version")
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            logger.error(f"Failed to get Podman version: {e}")
            return {}
    
    def _data_to_container_info(self, data: Dict[str, Any]) -> ContainerInfo:
        """将API数据转换为ContainerInfo"""
        try:
            # 获取端口映射
            ports = {}
            if data.get('NetworkSettings', {}).get('Ports'):
                for container_port, host_ports in data['NetworkSettings']['Ports'].items():
                    if host_ports:
                        ports[container_port] = f"{host_ports[0]['HostIp']}:{host_ports[0]['HostPort']}"
            
            # 获取卷挂载
            volumes = {}
            if data.get('Mounts'):
                for mount in data['Mounts']:
                    if mount.get('Type') == 'bind':
                        volumes[mount['Source']] = mount['Destination']
            
            return ContainerInfo(
                id=data.get('Id', ''),
                name=data.get('Names', [''])[0].lstrip('/') if data.get('Names') else data.get('Name', '').lstrip('/'),
                image=data.get('Image', ''),
                status=data.get('State', {}).get('Status', data.get('Status', '')),
                created=data.get('Created', ''),
                ports=ports,
                volumes=volumes,
                network=list(data.get('NetworkSettings', {}).get('Networks', {}).keys())[0] if data.get('NetworkSettings', {}).get('Networks') else None,
                ip_address=list(data.get('NetworkSettings', {}).get('Networks', {}).values())[0].get('IPAddress') if data.get('NetworkSettings', {}).get('Networks') else None
            )
        except Exception as e:
            logger.error(f"Failed to convert Podman data to container info: {e}")
            return ContainerInfo(
                id=data.get('Id', ''),
                name=data.get('Names', ['unknown'])[0] if data.get('Names') else 'unknown',
                image=data.get('Image', 'unknown'),
                status=data.get('Status', 'unknown'),
                created=data.get('Created', 'unknown')
            )
    
    def _data_to_image_info(self, data: Dict[str, Any]) -> ImageInfo:
        """将API数据转换为ImageInfo"""
        try:
            repo_tags = data.get('RepoTags', ['<none>:<none>'])
            if repo_tags and repo_tags[0] != '<none>:<none>':
                repo_tag = repo_tags[0].split(':')
                repository = repo_tag[0]
                tag = repo_tag[1] if len(repo_tag) > 1 else 'latest'
            else:
                repository = '<none>'
                tag = '<none>'
            
            return ImageInfo(
                id=data.get('Id', '')[:12],
                repository=repository,
                tag=tag,
                size=f"{data.get('Size', 0) / 1024 / 1024:.1f}MB",
                created=data.get('Created', 'unknown')
            )
        except Exception as e:
            logger.error(f"Failed to convert Podman data to image info: {e}")
            return ImageInfo(
                id=data.get('Id', 'unknown')[:12],
                repository='unknown',
                tag='unknown',
                size='unknown',
                created='unknown'
            )
    
    def _parse_memory(self, memory_str: str) -> int:
        """解析内存字符串为字节数"""
        try:
            memory_str = memory_str.upper()
            if memory_str.endswith('GB'):
                return int(float(memory_str[:-2]) * 1024 * 1024 * 1024)
            elif memory_str.endswith('MB'):
                return int(float(memory_str[:-2]) * 1024 * 1024)
            elif memory_str.endswith('KB'):
                return int(float(memory_str[:-2]) * 1024)
            else:
                return int(memory_str)
        except:
            return 0