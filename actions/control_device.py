import asyncio  # noqa: D100, INP001
import json
import re

from ..actions.action import Action  # noqa: TID252
from ..configs import CONFIG  # noqa: TID252
from ..llm import LLM  # noqa: TID252
from ..message import Message  # noqa: TID252
from ..tool_agent import (  # noqa: TID252
    map_tool_agent,
    time_tool_agent,
    weather_tool_agent,
)
from ..translator import Translator  # noqa: TID252
from ..utils.logs import _logger  # noqa: TID252

SYSTEM_MESSAGE = """
# Role
你是DeviceControler，你的任务是将用户请求解析为设备指令。

# Command Format
命令必须遵循以下格式：
id.service.property = <value>
设备的服务信息的层次必须被遵守（例如，speaker是television的子服务，因此音量应设置在3.television.speaker服务中设置，而不是3.television）。
特别地，如果你想修改空调的目标温度，你应生成如下格式的指令：id.air_conditioner.target_temperature = <value>

# Input
1. User request：用户请求。
2. Device list：包含设备信息，包括ID、类型、区域和可用服务。每个服务都有特定的属性。
3. Tool list：可用工具及其功能和所需参数。
4. Sensor data：所有附加到室内设备的传感器的当前数据。每组传感器信息的ID与其所属设备的ID匹配。
5. Dependency task information：当前任务所依赖的任务信息。

# Solution
1. 仅在能够充分判断所有前提条件的情况下，根据用户请求生成指令。
2. 如果可用信息不足，采取以下行动之一：
    1. 询问用户澄清信息。
    2. 调用工具获取帮助。
3. 你只能为需要立即执行的用户请求生成指令。如果发现设备控制不是立即执行的（例如，用户的请求涉及等待设备状态变化后再控制另一个设备，或等待一段时间后再控制设备），你需要向其他智能体寻求帮助。在这种情况下，你应选择 SeekHelp 动作类型。
   但如果你能准确判断当前任务依赖的具体前提信息（例如，是否立即执行取决于另一个设备的运行状态，而该状态已在依赖任务信息中提供），你仍然应生成指令，而不是寻求其他智能体的帮助。
   你必须记住，即使需要向其他智能体寻求帮助，你仍然需要评估当前任务的所有前提条件。你转交给其他智能体的任务应仅涉及控制设备，且不应包含其他前提条件，因为这些前提条件需要由你进行评估。

# Action Types
Finish：执行指令并向用户确认。
AskUser：请求更多信息。
CallTools：使用外部工具获取帮助。
SeekHelp：仅在用户的请求不能立即执行时，向其他智能体请求帮助。

# Output Format (In JSON type)
AskUser：
{"Action_type": "AskUser", "Thought": "请求用户输入的原因", "Say_to_user": "向用户的询问内容"}
CallTools：
{"Action_type": "CallTools", "Thought": "调用工具的原因", "Arguments": "所需参数", "Target_tool": "具体工具名称"}
Finish：
{"Action_type": "Finish", "Thought": "采取行动的原因", "Commands": ["生成的指令"], "Say_to_user": "向用户的确认内容"}
SeekHelp：
{"Action_type": "SeekHelp", "Thought": "寻求帮助的原因", "Say_to_agent": "需要完成的任务，此部分必须用中文"}

# Examples
示例 1：
用户：我现在开车从学校出发，如果晚上九点五十到不了家而且今天气温比较低的话，半小时后帮我打开卧室的空调。
DeviceControler：
{
    "Action_type": "CallTools",
    "Thought": "用户请求在 21:50 之前如果未到家且天气寒冷，则在 30 分钟后打开卧室空调。首先，我需要确定用户届时是否会晚归。",
    "Arguments": "["school", "home", "driving"]",
    "Target_tool": "PathPlanning"
}
观察结果：从用户的家到目的地驾车所需时间为：26.35分钟
DeviceControler：
{
    "Action_type": "CallTools",
    "Thought": "用户之前请求如果 21:50 还没到家且天气寒冷，则打开卧室空调。由于从学校到家的车程约为 26.35 分钟，我需要根据用户的出发时间计算实际到达时间，并与 21:50 进行比较。我还需要检查用户家附近的天气情况，以判断是否确实寒冷。",
    "Arguments": "",
    "Target_tool": "Time"
}
观察结果：当前时间是：2025-01-31 21:47:41
DeviceControler：
{
    "Action_type": "CallTools",
    "Thought": "为了判断室外是否寒冷，我需要调用 WeatherInformation 工具获取用户家位置的当前温度。",
    "Arguments": "",
    "Target_tool": "WeatherInformation"
}
观察结果：用户家所在区域的气象信息是<省略的具体气象信息>
DeviceControler：
{
    "Action_type": "SeekHelp",
    "Thought": "根据时间、交通和气温信息，我判断根据用户请求，应在 30 分钟后打开空调。由于该指令不是立即执行的，我需要寻求其他智能体的帮助。",
    "Say_to_agent": "半小时后打开卧室的空调。"
}

# Important Notes
1. 每次回复仅执行一个动作。如果需要多个输入，应逐步请求。
2. 仅修改具有write权限的属性。如果属性为只读，需通知用户。
3. 仔细分析用户请求的每个前提，确保所有前提都得到充分支持后再发布指令。不得假设任何信息。
4. 如果需要检查当前时间，必须调用 Time 工具。
5. 传感器数据仅反映室内环境数据，不能代表天气状况。
6. 请注意，如果你想修改空调的目标温度，你应生成如下格式的指令：id.air_conditioner.target_temperature = <value>
7. 你必须仅输出一个JSON字符串，不包含其他任何内容。
"""

USER_MESSAGE = """
User request: {user_request}
Device list: {device_list}
Tool list: {tool_list}
Sensor data: {sensor_data}
Dependency task information: {dependency_task_info}
"""

TOOL_MESSAGE = """
Tool return information: {tool_return}
"""


class ControlDevice(Action):
    def __init__(self, name="DeviceControler", context=None):
        super().__init__(name, context)
        self.llm = LLM()
        # TODO Agent不能准确识别需要调用时间工具的情况，考虑将时间直接输入
        self.tool_agent = [weather_tool_agent(), map_tool_agent(), time_tool_agent()]
        self.time = time_tool_agent()
        self.tool_list = self.tool_agent_to_tool_list()
        self.tool_dict = self.tool_agent_to_tool_dict()

    def parse_output(self, output: str) -> dict:
        """将LLM的输出转换为JSON字符串."""
        match = re.search(r"```json\s*(.*?)\s*```", output, re.DOTALL)
        if match:
            return json.loads(match.group(1).strip())
        return json.loads(output.strip())

    async def run(self, history_msg: list[Message], input: Message) -> Message:
        _logger.info(f"DeviceControler run: {input}")

        if not self.llm.sysmsg_added:
            self.llm.add_system_msg(SYSTEM_MESSAGE)

        all_context = CONFIG.hass_data["all_context"]
        sensor_data = CONFIG.hass_data["all_sensor_data"]
        curr_time = await self.time.run(None)

        if input.attachment is not None:
            # 依赖信息附加在input的attachment中
            dependency = f"current time:{curr_time}\n{input.attachment.content}"
        else:
            dependency = f"current time:{curr_time}\n"

        if input.role == "Tool":
            self.llm.add_user_msg(
                TOOL_MESSAGE.format(tool_return=input.content)
            )  # 如果是工具的返回，会忽略input.attachment
        else:
            self.llm.add_user_msg(
                USER_MESSAGE.format(
                    user_request=input.content,
                    device_list=all_context,
                    tool_list=self.tool_list,
                    sensor_data=sensor_data,
                    dependency_task_info=dependency,
                )
            )

        loop = asyncio.get_running_loop()
        rsp = await loop.run_in_executor(
            None, self.llm.chat_completion_text_v1, self.llm.history
        )
        _logger.info(f"ControlDevice response: {rsp}")
        print(rsp)
        rsp_json = self.parse_output(rsp)
        self.llm.add_assistant_msg(rsp)  # llm的回复加入记忆
        _logger.info(f"DeviceControler rsp: {rsp}")

        if rsp_json["Action_type"] == "Finish":
            # 结束任务，执行命令，返回信息发给用户（发布到环境中）
            self.llm.reset()
            say_to_user = rsp_json["Say_to_user"]
            if "Commands" in rsp_json:
                commands = rsp_json["Commands"]
                TRANSLATOR = Translator()
                for command in commands:
                    await TRANSLATOR.run_single_command(command)
            return Message(
                role=self.name,
                content=say_to_user,
                sent_from="DeviceControler",
                send_to=["User"],
                cause_by="Finish",
            )

        if rsp_json["Action_type"] == "AskUser":
            # 询问用户，返回信息发给用户（发布到环境中）
            say_to_user = rsp_json["Say_to_user"]
            return Message(
                role=self.name,
                content=say_to_user,
                sent_from="DeviceControler",
                send_to=["User"],
                cause_by="AskUser",
            )

        if rsp_json["Action_type"] == "CallTools":
            # 调用工具，工具返回的信息作为观察（observation）发回给自己
            target_tool = rsp_json["Target_tool"]
            arguments = rsp_json["Arguments"]
            for tool in self.tool_list:
                if tool["name"] == target_tool:
                    tool_rsp = await self.tool_dict[target_tool].run(arguments)
                    return Message(
                        role="Tool",
                        content="Observation:" + tool_rsp,
                        sent_from=target_tool,
                        send_to=["DeviceControler"],
                        cause_by="UserResponse",
                        attachment=Message(
                            role="DeviceControler",
                            content=rsp,
                            sent_from="DeviceControler",
                            send_to=["Tool"],
                            cause_by="AskUser",
                            attachment=None,
                        ),
                    )
            # 若没有找到对应的工具：返回工具不可用的信息
            return Message(
                role="Tool",
                content=f"Observation: no available tool named {target_tool}",
                sent_from="SYSTEM",
                send_to=["DeviceControler"],
                cause_by="SYSTEM",
            )

        if rsp_json["Action_type"] == "SeekHelp":
            task = rsp_json["Say_to_agent"]
            # 用户需求不是可以立即执行的命令，请求帮助，将信息发给TAPGenerator尝试执行
            return Message(
                role=self.name,
                content=task,
                sent_from="DeviceControler",
                send_to=["TAPGenerator"],
                cause_by="UserInput",
                attachment=Message(
                    role=self.name,
                    content=dependency,  # 请求TAPGenerator时附带依赖信息
                    sent_from="DeviceControler",
                    send_to=["TAPGenerator"],
                    cause_by="SYSTEM",
                ),
            )

        # 处理不正确的Action_type，让LLM重新生成回复
        return Message(
            role="SYSTEM",
            content="Incorrect action type, please generate correct response.",
            sent_from="SYSTEM",
            send_to=["DeviceControler"],
            cause_by="SYSTEM",
        )

    def reset(self):
        self.llm.reset()
        _logger.info(f"{self.name} reset.")
