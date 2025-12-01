from src.HostObject.VMConfig import VMConfig


class VRestAPI:
    def __init__(self,
                 host_addr="127.0.0.1:8697",
                 user_name="root",
                 pass_word="<PASSWORD>",
                 ver_agent=21):
        self.host_addr = host_addr
        self.user_name = user_name
        self.pass_word = pass_word
        self.ver_agent = ver_agent

    @staticmethod
    # 创建vmx文本 =========================================================
    def create_txt(in_config: dict, prefix: str = ""):
        result = ""
        for key, value in in_config.items():
            if isinstance(value, dict):
                # 如果值是字典，递归处理
                new_prefix = f"{prefix}{key}." if prefix else f"{key}."
                result += VRestAPI.create_txt(value, new_prefix)
            else:
                # 如果值不是字典，直接生成配置行
                full_key = f"{prefix}{key}" if prefix else key
                if type(value) == str:
                    result += f"{full_key} = \"{value}\"\n"
                else:
                    result += f"{full_key} = {value}\n"
        return result

    # 创建虚拟机 ======================================
    def create_vmx(self, vm_config: VMConfig = None):
        config = {
            ".encoding": "GBK",
            "config.version": "8",
            "virtualHW.version": str(self.ver_agent),
            "mks.enable3d": "TRUE",
            "pciBridge0": {
                "present": "TRUE"
            },
            "pciBridge4": {
                "present": "TRUE",
                "virtualDev": "pcieRootPort",
                "functions": "8"
            },
            "vmci0": {
                "present": "TRUE"
            },
            "hpet0": {
                "present": "TRUE"
            },
            "nvram": vm_config.vm_uuid + ".nvram",
            "virtualHW.productCompatibility": "hosted",
            "displayName": vm_config.vm_uuid,
            "firmware": "efi",
            "guestOS": "windows9-64",
            "numvcpus": str(vm_config.cpu_num),
            "cpuid.coresPerSocket": str(vm_config.cpu_num),
            "memsize": str(vm_config.mem_num),
            "mem.hotadd": "TRUE",
            "nvme0": {
                "present": "TRUE",
            },
            "nvme0:0": {
                "fileName": vm_config.vm_uuid + ".vmdk",
                "present": "TRUE"
            },
            "usb": {
                "present": "TRUE"
            },
            "ehci": {
                "present": "TRUE"
            },
            "usb_xhci": {
                "present": "TRUE"
            },
            "svga.graphicsMemoryKB": str(vm_config.gpu_mem * 1024),
            "ethernet0": {
                "connectionType": "nat",
                "addressType": "generated",
                "virtualDev": "e1000e",
                "present": "TRUE"
            },
            "extendedConfigFile": vm_config.vm_uuid + ".vmxf",
            "RemoteDisplay": {
                "vnc": {
                    "enabled": "TRUE",
                    "port": "5901"
                }
            },

        }
        # config = {**config, **basic_config}
        return VRestAPI.create_txt(config)

    # 配置虚拟机 ======================================
    def config_vmx(self, vm_config: VMConfig = None):
        pass

    # 删除虚拟机 ======================================
    def delete_vmx(self, vm_config: VMConfig = None):
        pass

    # 虚拟机电源 ======================================
    def powers_vmx(self, vm_config: VMConfig = None):
        pass

    # 虚拟机状态 ======================================
    def status_vmx(self, vm_config: VMConfig = None):
        pass


if __name__ == "__main__":
    vm_client = VRestAPI()
    vm_config = VMConfig()
    vm_config.vm_uuid = "Tests-All"
    vm_config.cpu_num = 4
    vm_config.mem_num = 2048
    vm_config.hdd_num = 10240
    vm_config.gpu_num = 0
    vm_config.net_num = 100
    vm_config.flu_num = 100
    vm_config.nat_num = 100
    vm_config.web_num = 100
    vm_config.gpu_mem = 4096

    vm_string = vm_client.create_vmx(vm_config)
    print(vm_string)
    with open(vm_config.vm_uuid + ".vmx", "w", encoding="utf-8") as save_file:
        save_file.write(vm_string)
