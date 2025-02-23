import asyncio

from pydantic import BaseModel, Field

from .configs import CONFIG
from .memory import Memory
from .message import Message
from .roles.chatbot import Chatbot
from .roles.device_controler import DeviceControler
from .roles.role import Role
from .roles.tap_generator import TapGenerator
from .utils.logs import _logger


class Environment(BaseModel):
    roles: dict[str, Role] = Field(default_factory=dict)
    memory: Memory = Field(default_factory=Memory)
    history: str = Field(default="")
    message_cnt: int = Field(default=0)
    devices: list = Field(default_factory=list)
    model_zoo: list = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self):
        super().__init__()
        self.devices = CONFIG.hass_data["all_context"]
        _logger.debug(f"devices number: {len(self.devices)}")
        self.add_roles(
            [DeviceControler(), TapGenerator(), Chatbot()]
        )  # 将角色添加到环境中，后续开发者可以根据自己的需求添加角色

    def add_role(self, role: Role):
        """增加一个在当前环境的Role."""
        role.set_env(self)  # 李安：将当前环境（Jarvis的环境）设置为role的环境
        self.roles[role.profile] = role

    def add_roles(self, roles: list[Role]):
        """增加一批在当前环境的Role."""
        for role in roles:
            self.add_role(role)

    async def publish_message(self, message: Message):
        """向当前环境发布信息."""
        self.memory.add(message)
        self.history += f"\n{message}"
        self.message_cnt += 1

    async def run(self, k=10) -> tuple[Message, bool]:
        """Jarvis发布一次信息后，角色再环境中并发运行."""
        # 默认允许角色之间对话10轮
        _logger.info("-----------------run-----------------")
        current_message_cnt = self.message_cnt
        for i in range(k):
            _logger.info(f"-----------------{i}-----------------")
            # 判断是否有新消息，如果没有则退出
            if i != 0 and self.message_cnt == current_message_cnt:
                break  # 一轮中没有任何新消息产生
            current_message_cnt = self.message_cnt

            futures = []
            for key in self.roles:
                role = self.roles[key]
                future = role.run()  # future是一个协程
                futures.append(future)  # 将协程添加到futures列表中
            await asyncio.gather(
                *futures
            )  # role.run()方法中await self._publish_message(rsp_message)这一行已经将rsp_message发布到环境中了，所以这里无需关注返回值
        latest_message = self.memory.get_latest_message()

        _logger.info(f"latest_message: {latest_message.to_dict()}")
        if latest_message.cause_by not in ["AskUser", "Finish"]:
            return ("运行出错，请检查", True)
        if latest_message.cause_by == "Finish":
            return (latest_message, True)
        if latest_message.cause_by == "AskUser":
            return (latest_message, False)
        return None

    def get_roles(self):
        """获得环境内的所有Role."""
        return self.roles

    def get_role(self, role_name: str) -> Role:
        """获得环境内的指定Role."""
        return self.roles.get(role_name, None)

    def reset(self):
        """重置环境."""
        self.memory = Memory()
        self.history = ""
        self.message_cnt = 0
        for key in self.roles:
            role = self.roles[key]
            role.reset()
