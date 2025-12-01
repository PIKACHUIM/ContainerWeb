class HSConfig:
    def __init__(self, **kwargs):
        self.server_type: str = ""  # 服务器类型
        self.server_addr: str = ""  # 服务器地址
        self.server_user: str = ""  # 服务器用户
        self.server_pass: str = ""  # 服务器密码
        self.filter_name: str = ""  # 过滤器名称
        self.images_path: str = ""  # 镜像存储池
        self.system_path: str = ""  # 系统存储池
        self.backup_path: str = ""  # 备份存储池
        self.extern_path: str = ""  # 数据存储池
