import docker
from docker.errors import DockerException, NotFound, APIError
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from .base import ContainerEngine, ContainerConfig, ContainerInfo, ImageInfo

logger = logging.getLogger(__name__)

class DockerEngine(ContainerEngine):
    """Docker容器引擎实现"""
    
    def _initialize_client(self, **kwargs):
        """初始化Docker客户端"""
        try:
            if self.host:
                self.client = docker.DockerClient(base_url=self.host)
            else:
                self.client = docker.from_env()
            logger.info(f"Docker client initialized with host: {self.host or 'default'}")
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise
    
    def ping(self) -> bool:
        """检查Docker连接状态"""
        try:
            self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Docker ping failed: {e}")
            return False
    
    def create_container(self, config: ContainerConfig) -> str:
        """创建Docker容器"""
        try:
            # 构建容器配置
            container_config = {
                'image': config.image,
                'name': config.name,
                'detach': True
            }
            
            # 端口映射
            if config.ports:
                container_config['ports'] = config.ports
            
            # 卷挂载
            if config.volumes:
                container_config['volumes'] = config.volumes
            
            # 环境变量
            if config.environment:
                container_config['environment'] = config.environment
            
            # 网络
            if config.network:
                container_config['network'] = config.network
            
            # 资源限制
            if config.cpu_limit or config.memory_limit:
                container_config['mem_limit'] = config.memory_limit
                container_config['cpu_quota'] = int(config.cpu_limit * 100000) if config.cpu_limit else None
                container_config['cpu_period'] = 100000 if config.cpu_limit else None
            
            # 特权模式
            if config.privileged:
                container_config['privileged'] = True
            
            # 设备映射
            if config.devices:
                container_config['devices'] = config.devices
            
            # 命令
            if config.command:
                container_config['command'] = config.command
            
            # 工作目录
            if config.working_dir:
                container_config['working_dir'] = config.working_dir
            
            # 用户
            if config.user:
                container_config['user'] = config.user
            
            # 重启策略
            if config.restart_policy:
                container_config['restart_policy'] = {"Name": config.restart_policy}
            
            container = self.client.containers.create(**container_config)
            logger.info(f"Container created: {container.id}")
            return container.id
            
        except Exception as e:
            logger.error(f"Failed to create container: {e}")
            raise
    
    def start_container(self, container_id: str) -> bool:
        """启动容器"""
        try:
            container = self.client.containers.get(container_id)
            container.start()
            logger.info(f"Container started: {container_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to start container {container_id}: {e}")
            return False
    
    def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """停止容器"""
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=timeout)
            logger.info(f"Container stopped: {container_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop container {container_id}: {e}")
            return False
    
    def restart_container(self, container_id: str, timeout: int = 10) -> bool:
        """重启容器"""
        try:
            container = self.client.containers.get(container_id)
            container.restart(timeout=timeout)
            logger.info(f"Container restarted: {container_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to restart container {container_id}: {e}")
            return False
    
    def remove_container(self, container_id: str, force: bool = False) -> bool:
        """删除容器"""
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=force)
            logger.info(f"Container removed: {container_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove container {container_id}: {e}")
            return False
    
    def get_container(self, container_id: str) -> Optional[ContainerInfo]:
        """获取容器信息"""
        try:
            container = self.client.containers.get(container_id)
            return self._container_to_info(container)
        except NotFound:
            return None
        except Exception as e:
            logger.error(f"Failed to get container {container_id}: {e}")
            return None
    
    def list_containers(self, all: bool = False) -> List[ContainerInfo]:
        """列出容器"""
        try:
            containers = self.client.containers.list(all=all)
            return [self._container_to_info(container) for container in containers]
        except Exception as e:
            logger.error(f"Failed to list containers: {e}")
            return []
    
    def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        """获取容器日志"""
        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(tail=tail, timestamps=True)
            return logs.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to get logs for container {container_id}: {e}")
            return ""
    
    def exec_command(self, container_id: str, command: str) -> Dict[str, Any]:
        """在容器中执行命令"""
        try:
            container = self.client.containers.get(container_id)
            exec_result = container.exec_run(command)
            return {
                'exit_code': exec_result.exit_code,
                'output': exec_result.output.decode('utf-8')
            }
        except Exception as e:
            logger.error(f"Failed to exec command in container {container_id}: {e}")
            return {'exit_code': -1, 'output': str(e)}
    
    def pull_image(self, image: str, tag: str = "latest") -> bool:
        """拉取镜像"""
        try:
            full_image = f"{image}:{tag}"
            self.client.images.pull(image, tag=tag)
            logger.info(f"Image pulled: {full_image}")
            return True
        except Exception as e:
            logger.error(f"Failed to pull image {image}:{tag}: {e}")
            return False
    
    def list_images(self) -> List[ImageInfo]:
        """列出镜像"""
        try:
            images = self.client.images.list()
            return [self._image_to_info(image) for image in images]
        except Exception as e:
            logger.error(f"Failed to list images: {e}")
            return []
    
    def remove_image(self, image_id: str, force: bool = False) -> bool:
        """删除镜像"""
        try:
            self.client.images.remove(image_id, force=force)
            logger.info(f"Image removed: {image_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove image {image_id}: {e}")
            return False
    
    def build_image(self, dockerfile_path: str, tag: str, build_args: Dict[str, str] = None) -> bool:
        """构建镜像"""
        try:
            self.client.images.build(
                path=dockerfile_path,
                tag=tag,
                buildargs=build_args or {}
            )
            logger.info(f"Image built: {tag}")
            return True
        except Exception as e:
            logger.error(f"Failed to build image {tag}: {e}")
            return False
    
    def commit_container(self, container_id: str, repository: str, tag: str = "latest") -> str:
        """将容器保存为镜像"""
        try:
            container = self.client.containers.get(container_id)
            image = container.commit(repository=repository, tag=tag)
            logger.info(f"Container committed to image: {repository}:{tag}")
            return image.id
        except Exception as e:
            logger.error(f"Failed to commit container {container_id}: {e}")
            raise
    
    def create_network(self, name: str, driver: str = "bridge", subnet: str = None) -> str:
        """创建网络"""
        try:
            network_config = {'driver': driver}
            if subnet:
                network_config['ipam'] = docker.types.IPAMConfig(
                    pool_configs=[docker.types.IPAMPool(subnet=subnet)]
                )
            
            network = self.client.networks.create(name, **network_config)
            logger.info(f"Network created: {name}")
            return network.id
        except Exception as e:
            logger.error(f"Failed to create network {name}: {e}")
            raise
    
    def list_networks(self) -> List[Dict[str, Any]]:
        """列出网络"""
        try:
            networks = self.client.networks.list()
            return [self._network_to_dict(network) for network in networks]
        except Exception as e:
            logger.error(f"Failed to list networks: {e}")
            return []
    
    def remove_network(self, network_id: str) -> bool:
        """删除网络"""
        try:
            network = self.client.networks.get(network_id)
            network.remove()
            logger.info(f"Network removed: {network_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove network {network_id}: {e}")
            return False
    
    def connect_container_to_network(self, container_id: str, network_id: str) -> bool:
        """将容器连接到网络"""
        try:
            network = self.client.networks.get(network_id)
            network.connect(container_id)
            logger.info(f"Container {container_id} connected to network {network_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect container {container_id} to network {network_id}: {e}")
            return False
    
    def disconnect_container_from_network(self, container_id: str, network_id: str) -> bool:
        """将容器从网络断开"""
        try:
            network = self.client.networks.get(network_id)
            network.disconnect(container_id)
            logger.info(f"Container {container_id} disconnected from network {network_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to disconnect container {container_id} from network {network_id}: {e}")
            return False
    
    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        try:
            return self.client.info()
        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            return {}
    
    def get_version(self) -> Dict[str, Any]:
        """获取Docker版本信息"""
        try:
            return self.client.version()
        except Exception as e:
            logger.error(f"Failed to get version: {e}")
            return {}
    
    def _container_to_info(self, container) -> ContainerInfo:
        """将Docker容器对象转换为ContainerInfo"""
        try:
            container.reload()
            attrs = container.attrs
            
            # 获取端口映射
            ports = {}
            if attrs.get('NetworkSettings', {}).get('Ports'):
                for container_port, host_ports in attrs['NetworkSettings']['Ports'].items():
                    if host_ports:
                        ports[container_port] = f"{host_ports[0]['HostIp']}:{host_ports[0]['HostPort']}"
            
            # 获取卷挂载
            volumes = {}
            if attrs.get('Mounts'):
                for mount in attrs['Mounts']:
                    if mount['Type'] == 'bind':
                        volumes[mount['Source']] = mount['Destination']
            
            # 获取网络信息
            network = None
            ip_address = None
            if attrs.get('NetworkSettings', {}).get('Networks'):
                networks = attrs['NetworkSettings']['Networks']
                if networks:
                    network_name = list(networks.keys())[0]
                    network = network_name
                    ip_address = networks[network_name].get('IPAddress')
            
            return ContainerInfo(
                id=container.id,
                name=container.actions.lstrip('/'),
                image=attrs['Config']['Image'],
                status=container.status,
                created=attrs['Created'],
                ports=ports,
                volumes=volumes,
                network=network,
                ip_address=ip_address
            )
        except Exception as e:
            logger.error(f"Failed to convert container to info: {e}")
            return ContainerInfo(
                id=container.id,
                name=container.actions.lstrip('/'),
                image="unknown",
                status=container.status,
                created="unknown"
            )
    
    def _image_to_info(self, image) -> ImageInfo:
        """将Docker镜像对象转换为ImageInfo"""
        try:
            tags = image.tags or ['<none>:<none>']
            repo_tag = tags[0].split(':')
            repository = repo_tag[0] if len(repo_tag) > 1 else tags[0]
            tag = repo_tag[1] if len(repo_tag) > 1 else 'latest'
            
            return ImageInfo(
                id=image.id.split(':')[1][:12],
                repository=repository,
                tag=tag,
                size=f"{image.attrs.get('Size', 0) / 1024 / 1024:.1f}MB",
                created=image.attrs.get('Created', 'unknown')
            )
        except Exception as e:
            logger.error(f"Failed to convert image to info: {e}")
            return ImageInfo(
                id=image.id.split(':')[1][:12] if ':' in image.id else image.id[:12],
                repository="unknown",
                tag="unknown",
                size="unknown",
                created="unknown"
            )
    
    def _network_to_dict(self, network) -> Dict[str, Any]:
        """将Docker网络对象转换为字典"""
        try:
            return {
                'id': network.id,
                'name': network.actions,
                'driver': network.attrs.get('Driver', 'unknown'),
                'scope': network.attrs.get('Scope', 'unknown'),
                'created': network.attrs.get('Created', 'unknown'),
                'subnet': network.attrs.get('IPAM', {}).get('Config', [{}])[0].get('Subnet', 'unknown') if network.attrs.get('IPAM', {}).get('Config') else 'unknown'
            }
        except Exception as e:
            logger.error(f"Failed to convert network to dict: {e}")
            return {
                'id': network.id,
                'name': network.actions,
                'driver': 'unknown',
                'scope': 'unknown',
                'created': 'unknown',
                'subnet': 'unknown'
            }