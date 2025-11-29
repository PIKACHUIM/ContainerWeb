import json


class ZMessage:
    def __init__(self, ):
        self.success: bool = True
        self.actions: str = ""
        self.message: str = ""
        self.results: dict = {}
        self.execute: Exception | None = None

    # 转换为字典 ============================
    def __dict__(self):
        return {
            "success": self.success,
            "actions": self.message,
            "results": self.results,
            "execute": repr(self.execute)
        }

    # 转换为字符串 ==========================
    def __str__(self):
        return json.dumps({self.__dict__()})
