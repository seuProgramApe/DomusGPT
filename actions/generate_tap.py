import asyncio
import json

from ..actions.action import Action
from ..configs import CONFIG
from ..llm import LLM
from ..message import Message
from ..translator import Translator
from ..utils.logs import _logger
from ..tool_agent import time_tool_agent

SYSTEM_MESSAGE_2 = """
# 角色
您是智能家居领域中的有用助手，名为TAPGenerator。您的任务是将用户输入解析为触发-动作程序（trigger-action program）。

# 输入
1. 用户请求
2. 设备列表：与用户请求相关的设备信息，包括id、区域、类型和服务。每个设备的服务可能包含多个属性。
3. 依赖任务完成状态：如果用户的请求与其他设备控制任务的完成状态信息相关，则会提供此补充信息（例如：依赖任务是否完成或完成时间 ）。

# 解决方案
根据用户请求，您需要找到trigger、condition和action，然后找到相应的设备、服务及其属性。如果无法生成确切的TAP，您需要向用户询问更多信息。如果用户请求与依赖任务的完成时间相关，您需要解析出任务完成时间中的具体时间。
所以有两种Action_type：AskUser和Finish。
在AskUser类型中，您必须返回一个包含"Thought"、"Action_type"和"Say_to_user"的JSON。"Say_to_user"是向用户询问更多信息的回复。请注意，"Say_to_user"的语言应该与用户请求相同。
在Finish类型中，您必须返回一个包含"Thought"、"Action_type"、"TAP"和"Say_to_user"的JSON。
"Thought"是生成TAP的推理过程。"TAP"是一个JSON表达式，格式为{"trigger": <trigger>, "condition": <condition>, "action": <action>}。<trigger>、<condition>和<action>由基本元素" id.service.property<op><value>"组成。<op>在<trigger>和<condition>中选择"<"、">"或"=="，在<action>中则必须是"="。<value>是基于属性类型的各种类型的值，包括bool、int和string。在<trigger>和<action>中，元素之间用","分隔。在<condition>中，元素通过"&&"、"||"和"()"组合，如"condition_1&& (condition_2||condition_3)"。"Say_to_user"是告知用户的该自动化的详细信息。
如果trigger或condition是基于时间的，那么其格式如下：
如果用户仅指定日期，则使用"Date==YYYY-MM-DD"（例如，"Date==2025-01-30"）。
如果用户仅指定时间，则使用"Time==HH:MM"（24小时格式，例如，"Time==11:48"）。
如果用户同时指定时间和日期，则使用"Time & Date==HH:MM, YYYY-MM-DD"（例如，"Time & Date==11:48, 2025-01-30"）。
请注意，如果你需要通过推理来获得trigger或condition中的具体时间，那么你需要在"Say_to_user"的内容中明确告知用户该具体时间点。

# 示例
Example1:
User:
user request: 如果实验室的门打开了，就打开灯。
device list: [{"id":1,"area":"laboratory","type":"light","services":{"light":{"on":{"description":"开关状态","format":"bool","access":["read","write","notify"]},"brightness":{"description":"亮度","format":"uint16","access":["read","write","notify"],"unit":"percentage","value-range":[1,65535,1]},"color_temperature":{"description":"色温","format":"uint32","access":["read","write","notify"],"unit":"kelvin","value-range":[2700,6500,1]}}}},
{"id":2,"area":"laboratory","type":"magnet_sensor","services":{"magnet_sensor":{"contact_state":{"description":"接触状态","format":"bool","access":["read","notify"]}}}}]
Assistant:
{
    "Thought": "根据用户请求，使用实验室的磁性传感器作为trigger。设备ID为2，服务为magnet_sensor，属性为contact_state，值为true。实验室中的灯作为action，设备ID为1，服务为light，属性为on，值为true。",
    "TAP": {"trigger": "2.magnet_sensor.contact_state==true", "condition": "", "action": "1.light.on=true"},
    "Say_to_user": "好的，我已为您设置好，当实验室门打开时，灯会自动开启。",
    "Action_type": "Finish"
}

Example2:
User:
user request: 在空调关闭30分钟后打开加热器。
device list: [{"id":3,"area":"bedroom","type":"heater","services":{"heater":{"power":{"description":"电源","format":"bool","access":["read","write","notify"]}}}}]
dependency task completion status: {"current time": "2025-02-08 15:00", "dependency":[{"content": "关闭空调", "finish time": "2025-02-08 14:59"}]}
Assistant:
{
    "Thought": "用户希望在空调关闭30分钟后打开加热器。空调在2025-02-08 14:59关闭，所以加热器应在2025-02-08 15:29开启。trigger是Time & Date==15:29, 2025-02-08。加热器作为action，设备ID为3，服务为heater，属性为power，值为true。",
    "TAP": {"trigger": "Time & Date==15:29, 2025-02-08", "condition": "", "action": "3.heater.power=true"},
    "Say_to_user": "好的，我已经为您设置好，空调关闭30分钟后，也就是2025-02-08 15:29，自动开启加热器。",
    "Action_type": "Finish"
}
"""

USER_MESSAGE = """
user_request: {user_request}
device_list: {device_list}
dependency task completion status: {dependency_task_completion_status}
"""

FORMAT_EXAMPLE = """"""

OUTPUT_MAPPING = {}


class GenerateTAP(Action):
    def __init__(self, name="TAPGenerator", context=None):
        super().__init__(name, context)
        self.llm = LLM()
        self.user_request = None
        self.time = time_tool_agent()

    def parse_output(self, output: str) -> dict:
        # TODO error handling
        if output.startswith("```json"):
            output = output[7:]
            output = output[:-3]
            return json.loads(output.strip())
        elif output.startswith("```"):
            output = output[3:]
            output = output[:-3]
            return json.loads(output.strip())
        else:
            return json.loads(output.strip())

    async def run(self, history_msg: list[Message], user_input: Message) -> Message:
        _logger.info(f"TapGenerator run: {user_input}")
        if self.user_request is None:
            self.user_request = user_input.content
        user_request = user_input.content
        self.llm.add_system_msg(SYSTEM_MESSAGE_2)
        all_context = CONFIG.hass_data["all_context"]
        curr_time = await self.time.run(None)
        self.llm.add_user_msg(
            USER_MESSAGE.format(
                user_request=user_request,
                device_list=all_context,
                dependency_task_completion_status=curr_time,
            )
        )

        loop = asyncio.get_running_loop()
        rsp = await loop.run_in_executor(
            None, self.llm.chat_completion_json_v1, self.llm.history
        )
        print(f"TAPGenerator: {rsp}")
        _logger.info(f"TapGenerator rsp: {rsp}")
        # TODO error handling
        rsp_json = self.parse_output(rsp)

        if rsp_json["Action_type"] == "Finish":
            self.llm.reset()
            tap = rsp_json["TAP"]
            say_to_user = rsp_json["Say_to_user"]
            TRANSLATOR = Translator()

            # 判断即将生成的TAP是否只运行一次
            runOnce: bool = False
            if user_input.attachment.content == "TAP only run once":
                runOnce = True

            await TRANSLATOR.deploy_tap(runOnce, self.user_request, tap)
            self.user_request = None
            return Message(
                role=self.name,
                content=say_to_user,
                send_to=["User"],
                cause_by="Finish",
                sent_from="TAPGenerator",
            )

        if rsp_json["Action_type"] == "AskUser":
            say_to_user = rsp_json["Say_to_user"]
            self.llm.add_assistant_msg(say_to_user)
            return Message(
                role=self.name,
                content=say_to_user,
                send_to=["User"],
                cause_by="AskUser",
                sent_from="TAPGenerator",
            )

        # 处理错误的Action_type，让LLM重新生成正确的response
        return Message(
            role="SYSTEM",
            content="Incorrect action type, please generate correct response.",
            send_to=["TAPGenerator"],
            cause_by=None,
            sent_from=None,
        )

    def reset(self):
        self.user_request = None
        self.llm.reset()
        _logger.info(f"{self.name} reset.")
