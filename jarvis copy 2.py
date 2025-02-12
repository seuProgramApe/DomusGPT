from .utils.singleton import Singleton
from .environment import Environment
from .context_assistant import get_all_context
from .message import Message
from .utils.singleton import Singleton


# 这是原始的不支持多任务的Jarvis实现
class Jarvis(metaclass=Singleton):
    def __init__(self):
        self.environment = (
            Environment()
        )  # 李安：因为Jarvis是单例模式，所以Jarvis对应的环境是唯一的
        self.flag = True
        self.last_message_from = None

    async def run(self, request: str):
        if request == "刷新":
            get_all_context()
            self.flag = True
            self.last_message_from = None
            self.environment.reset()
            return "请问需要什么帮助？"

        if self.flag:  # 李安：如果flag为true，向环境发布的信息是用户输入，说明上一次的消息是由用户发出的请求，所以这次的消息要发给Manager
            await self.environment.publish_message(
                Message(
                    role="Jarvis",
                    content=request,
                    send_to=["Manager"],
                    sent_from="User",
                    cause_by="UserInput",
                )
            )
        elif self.last_message_from is None:
            raise Exception("last_message_from is None")
        else:  # 李安：如果flag为false，向环境发布的信息是用户回复，说明上一次的消息是由某个角色发出的向用户询问，所以这次的消息也要发给这个角色
            await self.environment.publish_message(
                Message(
                    role="Jarvis",
                    content=request,
                    send_to=[self.last_message_from],
                    sent_from="User",
                    cause_by="UserResponse",
                )
            )
        msg, flag = await self.environment.run()
        if flag:  # 李安：如果环境运行得到的信息中的flag是True，说明resp_type是Finish，本次任务已经完成，需要重置环境
            self.flag = True
            self.last_message_from = None
            print("运行时上下文:")
            self.environment.roles["DeviceControler"]._rc.memory.print_memory_list()
            self.environment.reset()
        else:  # 李安：如果环境运行得到的信息中的flag是False，说明resp_type是AskUser，本次任务还未完成，需要继续
            self.flag = False
            self.last_message_from = msg.role  # 李安：msg.role记录了上一次信息是由哪个角色发出的，下一次信息要发给这个角色
        return msg.content


JARVIS = Jarvis()
