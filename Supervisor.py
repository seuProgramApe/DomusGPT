from copy import deepcopy
from datetime import datetime, timedelta
from queue import Queue

from .Router import Router
from .environment import Environment
from .message import Message
from .utils.singleton import Singleton
from .Synthesizer import Synthesizer


class Subtask:
    def __init__(self, id, content, time=None, msg=None, type=None, dependency=None):
        self.id: int = id
        self.content: str = content
        self.finsih_time: str = time
        self.finish_msg: Message = msg
        self.type: str = type
        self.dependency: list[int] = dependency

    def toStr(self):
        return f"Subtask:id={self.id}, content={self.content}, type={self.type}, dependency={self.dependency!s}, finish_time={self.finsih_time}"


class Supervisor(metaclass=Singleton):
    def __init__(self):
        self.environment = Environment()
        self.flag = True
        self.last_message_from = None
        self.task_que: Queue[Subtask] = Queue()  # 等待完成的子任务队列
        self.rspls: list = []  # 用于汇总所有已经完成的子任务的最后返回信息的content
        self.subtask_done: list[Subtask] = []  # 用于存储所有已经完成的子任务的列表
        self.subtask_todo: list[Subtask] = []  # 用于存储所有等待完成的子任务的列表
        self.curr_subtask: Subtask | None = None
        self.router = Router()
        self.synthesizer = Synthesizer()

    async def task_decomposition(self, request):
        """当且仅当子任务队列为空且self.flag为True时调用此方法,分解复杂任务,将子任务加入子任务队列."""
        print("Run task decomposition")
        rsp_list = await self.router.run(request)  # 返回分解任务后的子任务list
        for task in rsp_list:
            if "id" not in task:
                continue
            newSubtask = Subtask(
                id=task["id"],
                content=task["content"],
                type=task["type"],
                dependency=task["dependency"],
            )
            # 目前采用队列的FIFO方式决定任务执行顺序，每次执行子任务时，从队列中取出一个子任务，执行完毕后再取下一个
            self.task_que.put(newSubtask)
            # subtask_todo是为了生成DAG图，执行任务过程中不需要更新
            self.subtask_todo.append(newSubtask)
            # TODO 拓扑排序

    async def process(self, request: str):
        if self.task_que.empty() and self.flag:
            # 子任务队列为空且所有子任务都已经完成
            await self.task_decomposition(request)

        if self.flag:  # 如果flag为True，说明上一个子任务已经完成，需要执行新的子任务
            subtask: Subtask = self.task_que.get(block=False)  # 获取新任务
            self.curr_subtask = subtask
            print(f"Execute new subtask: {subtask.content}")

            dep: list[int] = subtask.dependency
            if len(dep) > 0:
                # 当subtask.dependecny非空时，说明该任务有依赖任务信息
                dep_info: str = ""
                for index in dep:
                    content = self.subtask_done[index - 1].content
                    finish_time = self.subtask_done[index - 1].finsih_time
                    finish_info = self.subtask_done[index - 1].finish_msg
                    dep_info += f"Subtask {index}: {content}, finish time: {finish_time}, finish info: {finish_info}\n"
                dep_info_message = Message(
                    role="Supervisor",
                    content=dep_info,
                    cause_by="Dependency_information",
                    sent_from="User",
                    send_to=[],
                )
                print("dependency_information: ", dep_info_message.to_Str())
            else:
                dep_info_message = None

            if subtask.type == "TAP generation":
                if dep_info_message is not None:
                    dep_info_message.send_to.append("TAPGenerator")
                await self.environment.publish_message(
                    Message(
                        role="Supervisor",
                        content=subtask.content,
                        send_to=["TAPGenerator"],
                        sent_from="User",
                        cause_by="UserInput",
                        attachment=dep_info_message,
                    )
                )

            elif subtask.type == "Device Control":
                if dep_info_message is not None:
                    dep_info_message.send_to.append("DeviceControler")
                await self.environment.publish_message(
                    Message(
                        role="Supervisor",
                        content=subtask.content,
                        send_to=["DeviceControler"],
                        sent_from="User",
                        cause_by="UserInput",
                        attachment=dep_info_message,
                    )
                )

            elif subtask.type == "General Q&A":
                if dep_info_message is not None:
                    dep_info_message.send_to.append("Chatbot")
                await self.environment.publish_message(
                    Message(
                        role="Supervisor",
                        content=subtask.content,
                        send_to=["Chatbot"],
                        sent_from="User",
                        cause_by="UserInput",
                        attachment=dep_info_message,
                    )
                )
            else:
                raise Exception("Unknown subtask type")

        else:  # 如果flag为False，说明上一个子任务还未完成，正在等待用户回复，所以需要将用户回复发送给上一个子任务的角色
            if self.last_message_from is None:
                raise Exception("last_message_from is None")
            await self.environment.publish_message(
                Message(
                    role="Supervisor",
                    content=request,
                    send_to=[self.last_message_from],
                    sent_from="User",
                    cause_by="UserResponse",
                )
            )

        msg, flag = await self.environment.run()

        if flag:  # 如果环境运行得到的信息中的flag是True，说明resp_type是Finish，本次任务已经完成，需要重置环境
            self.flag = True
            self.last_message_from = None
            self.environment.reset()

            self.rspls.append(
                f"subtask {self.curr_subtask.id}:{msg.content}"
            )  # 将本次任务的返回信息加入rspls

            now = datetime.now() + timedelta(hours=8)  # 正式发布时可能需要修改时区
            formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")  # 该任务完成的格式化时间

            curr_subtask: Subtask = deepcopy(self.curr_subtask)
            curr_subtask.finsih_time = formatted_time
            curr_subtask.finish_msg = msg
            self.subtask_done.append(curr_subtask)  # 该子任务已经完成，加入subtask_done

            print(f"{self.curr_subtask.content} done.")
            print("self.subtask_done(Supervisor.py, line 119):")
            for st in self.subtask_done:
                print(st.toStr())
            if self.task_que.empty():  # 所有子任务都已经处理完毕
                print("All subtasks done.")
                rsp = deepcopy(self.rspls)

                # 根据是否有多个子任务的返回信息，决定是否需要合成返回信息
                if len(rsp) == 1:
                    final_rsp = rsp[0].split(":", 1)[1]
                else:
                    final_rsp = await self.synthesizer.run(rsp)

                self.rspls.clear()
                self.subtask_done.clear()
                self.subtask_todo.clear()

                return final_rsp
            return None  # 如果返回None，说明还有子任务需要处理

        # 如果环境运行得到的信息中的flag是False，说明resp_type是AskUser，本次任务还未完成，需要继续
        self.flag = False
        self.last_message_from = (
            msg.role
        )  # msg.role记录了上一次信息是由哪个角色发出的，下一次信息要发给这个角色
        return msg.content

    async def run(self, request: str):  # noqa: D102
        # request 即 conversation[-1]["message"], 用户输入
        rsp = await self.process(request)
        while rsp is None:
            rsp = await self.process(request)
        if isinstance(rsp, list):
            return "\n".join(
                f"Subtask {i} response: {msg}" for i, msg in enumerate(rsp)
            )
        if isinstance(rsp, str):
            return rsp
        return "Error: illegal response type."


SUPERVISOR = Supervisor()
