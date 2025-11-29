from src.HostAgents.Template import BaseServer
from src.HostObject.HSConfig import HSConfig
from src.HostObject.VMPowers import VMPowers
from src.HostObject.HWStatus import HWStatus
from src.HostObject.ZMessage import ZMessage
from src.HostObject.VMConfig import VMConfig


class HostServer(BaseServer):
    def __init__(self, config: HSConfig):
        super().__init__(config)

    # 宿主机状态 ==========================================
    def HSStatus(self, in_time: int = 2592000) -> HWStatus:
        pass

    # 初始宿主机 ==========================================
    def HSCreate(self, input_config: HSConfig) -> ZMessage:
        pass

    # 还原宿主机 ==========================================
    def HSDelete(self, input_config: HSConfig) -> ZMessage:
        pass

    # 配置宿主机 ==========================================
    def HSConfig(self, input_config: HSConfig) -> ZMessage:
        pass

    # 宿主机操作 ==========================================
    def HSAction(self, action: str = "status") -> ZMessage:
        pass

    # 虚拟机列出 ==========================================
    def VMStatus(self, uuid: str | None) -> list[HWStatus]:
        pass

    # 创建虚拟机 ==========================================
    def VMCreate(self, input_config: VMConfig) -> ZMessage:
        pass

    # 配置虚拟机 ==========================================
    def VMConfig(self, input_config: VMConfig) -> ZMessage:
        pass

    # 删除虚拟机 ==========================================
    def VMDelete(self, uuid: str, p: VMPowers) -> ZMessage:
        pass

    # 虚拟机电源 ==========================================
    def VMPowers(self, uuid: str, p: VMPowers) -> ZMessage:
        pass
