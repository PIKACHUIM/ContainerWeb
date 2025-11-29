import json
from src.HostObject.HWUsages import CPU_Usage, MEM_Usage, HDD_Usage, GPU_Usage
from src.HostObject.HWUsages import PWR_Usage, NET_Usage, NAT_Usage, WEB_Usage
from src.HostObject.VMPowers import VMPowers as VPower


class HWStatus:
    def __init__(self, **kwargs):
        # 基础数据 ============================
        self.ac_status: VPower = VPower.UNKNOWN
        self.cpu_model: str = ""  # 当前CPU名称
        self.cpu_total: int = 0  # 当前核心总计
        self.cpu_usage: int = 0  # 当前核心已用
        self.mem_total: int = 0  # 当前内存总计
        self.mem_usage: int = 0  # 当前内存已用
        self.hdd_total: int = 0  # 当前磁盘总计
        self.hdd_usage: int = 0  # 当前磁盘已用
        # 网络信息 ============================
        self.flu_total: int = 0  # 当前流量总计
        self.flu_usage: int = 0  # 当前流量已用
        self.nat_total: int = 0  # 当前端口总计
        self.nat_usage: int = 0  # 当前端口已用
        self.web_total: int = 0  # 当前代理总计
        self.web_usage: int = 0  # 当前代理已用
        # 其他信息 ============================
        self.gpu_total: int = 0  # 当前显卡数量
        self.gpu_usage: dict = {}  # GPU 使用率
        self.net_total: int = 0  # 当前带宽总计
        self.net_usage: int = 0  # 当前带宽已用
        self.cpu_power: int = 0  # 当前核心温度
        self.pwr_usage: int = 0  # 当前核心功耗
        # 历史数据 ============================
        self.cpu_stats: CPU_Usage | None = None
        self.mem_stats: MEM_Usage | None = None
        self.hdd_stats: HDD_Usage | None = None
        self.gpu_stats: GPU_Usage | None = None
        self.net_stats: NET_Usage | None = None
        self.flu_stats: CPU_Usage | None = None
        self.nat_stats: NAT_Usage | None = None
        self.web_stats: WEB_Usage | None = None
        self.pwr_stats: PWR_Usage | None = None
        # 加载数据 ============================
        self.__load__(**kwargs)

    # 加载数据 ================================
    def __load__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    # 转换为字典 ==============================
    def __dict__(self):
        return {
            "cpu_model": self.cpu_model,
            "cpu_total": self.cpu_total,
            "cpu_usage": self.cpu_usage,
            "mem_total": self.mem_total,
            "mem_usage": self.mem_usage,
            "hdd_total": self.hdd_total,
            "hdd_usage": self.hdd_usage,
            "flu_total": self.flu_total,
            "flu_usage": self.flu_usage,
            "nat_total": self.nat_total,
            "nat_usage": self.nat_usage,
            "web_total": self.web_total,
            "web_usage": self.web_usage,
            "gpu_total": self.gpu_total,
            "gpu_usage": self.gpu_usage,
            "net_total": self.net_total,
            "net_usage": self.net_usage,
            "cpu_power": self.cpu_power,
            "pwr_usage": self.pwr_usage,
            "cpu_stats": self.cpu_stats,
            "mem_stats": self.mem_stats,
            "hdd_stats": self.hdd_stats,
            "gpu_stats": self.gpu_stats,
            "net_stats": self.net_stats,
            "flu_stats": self.flu_stats,
            "nat_stats": self.nat_stats,
            "web_stats": self.web_stats,
            "pwr_stats": self.pwr_stats,
        }

    # 转换为文本 ==============================
    def __str__(self):
        return json.dumps(self.__dict__())
