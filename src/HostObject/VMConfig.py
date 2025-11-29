class IPConfig:
    def __init__(self):
        self.ip_addr: str = ""
        self.ip_mask: str = ""

    def __dict__(self):
        return {
            "ip_addr": self.ip_addr,
            "ip_mask": self.ip_mask,
        }


class NCConfig:
    def __init__(self):
        self.mac_addr: str = ""
        self.ip4_addr: list[IPConfig] = []
        self.ip6_addr: list[IPConfig] = []

    def __dict__(self):
        return {
            "mac_addr": self.mac_addr,
            "ip4_addr": self.ip4_addr,
            "ip6_addr": self.ip6_addr,
        }


class VMConfig:
    def __init__(self, **kwargs):
        # 机器配置 ===========================
        self.vm_uuid = ""  # 设置虚拟机名-UUID
        self.cpu_num = 0  # 分配的处理器核心数
        self.mem_num = 0  # 分配内存数(单位MB)
        self.hdd_num = 0  # 分配硬盘数(单位MB)
        self.gpu_num = 0  # 分配显卡ID(0-没有)
        self.net_num = 0  # 分配带宽(单位Mbps)
        self.flu_num = 0  # 分配流量(单位Mbps)
        self.nat_num = 0  # 分配端口(0-不分配)
        self.web_num = 0  # 分配代理(0-不分配)
        self.nic_all: dict[str, NCConfig] = {}
        # 加载数据 ===========================
        self.__load__(**kwargs)

    # 加载数据 ===============================
    def __load__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    # 转换为字典 =============================
    def __dict__(self):
        return {
            "vm_uuid": self.vm_uuid,
            "cpu_num": self.cpu_num,
            "mem_num": self.mem_num,
            "hdd_num": self.hdd_num,
            "gpu_num": self.gpu_num,
            "net_num": self.net_num,
            "flu_num": self.flu_num,
            "nat_num": self.nat_num,
            "web_num": self.web_num,
            "nic_all": self.nic_all,
        }

    # 转换为字符串 ===========================
    def __str__(self):
        return json.dumps(self.__dict__())
