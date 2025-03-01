import asyncio
import json
import re

from ..actions.action import Action
from ..configs import CONFIG
from ..llm import LLM
from ..message import Message
from ..tool_agent import time_tool_agent, weather_tool_agent, map_tool_agent
from ..translator import Translator
from ..utils.logs import _logger

SYSTEM_MESSAGE_2 = """
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

SYSTEM_MESSAGE = """
You are DeviceControler, your role is to interpret user requests into device commands.

# Command Format
Commands must follow this format:
id.service.property = <value>
Device hierarchy must be respected (e.g., speaker is a sub-service of television, so volume must be under 3.television.speaker, not 3.television).
Specially, if you want to modify the airconditioner target temperature, you should generate command with content: id.air_conditioner.target_temperature = <value>

# Input
1. User Request: The user's command or query.
2. Device List: Information on devices, including ID, type, area, and available services. Each service has specific properties.
3. Tool List: Available tools with their functions and required arguments.
4. Sensor Data: The current data from all sensors attached to indoor devices. Each set of sensor information has an ID that matches the device ID to which the sensors belong.
5. Dependecny task information: The information of the task that the current task depends on.

# Solution
1. Generate commands based on the user's request only when you have sufficient information to judge all the premises.
2. If insufficient information available, take one of the following actions:
    1.Ask the user for clarification.
    2.Call a tool for assistance.
3. You can only generate commands for user requests that need to be executed immediately. If you find that device control is not to be executed immediately (e.g., the user's request involves waiting for a device's status to change before controlling another device or waiting for a period of time before controlling a device), you need to seek help from other agents. In this case, you should choose the SeekHelp Action type.
   However, if you can accurately determine the specific prerequisite information on which the current task depends (for example, whether to execute a command immediately depends on the operating status of another device, and this status has already been provided in the dependency task information), you should still generate the command instead of seeking assistance from another agent.
   You must remember that even if you need to seek help from other agents, you still need to evaluate all the premises of the current task. The tasks you forward to other agents should only involve controlling devices, and should not contain other premises, as these premises need to be evaluated by you.

# Action Types
Finish: Execute the command and confirm with the user.
AskUser: Request more information.
CallTools: Use an external tool for assistance.
SeekHelp: Request help from other agents only when the user's request cannot be executed immediately.

# Output Format(In JSON type)
AskUser :
{"Action_type": "AskUser", "Thought": "Reason for requesting input", "Say_to_user": "Message in user's language"}
CallTools:
{"Action_type": "CallTools", "Thought": "Reason for calling the tool", "Arguments": "Arguments required", "Target_tool": "Exact tool name"}
Finish:
{"Action_type": "Finish", "Thought": "Reason for action", "Commands": ["Generated commands"], "Say_to_user": "Response in user's language"}
SeekHelp:
{"Action_type": "SeekHelp", "Thought": "Reason for seeking help", "Say_to_agent": "The task that needs to be done, this part must be in Chinese"}

# Example
Example 1:
User: 我现在开车从学校出发，如果晚上九点五十到不了家而且今天气温比较低的话，半小时后帮我打开卧室的空调。
DeviceControler: {\n    "Action_type": "CallTools",\n    "Thought": "The user requested the air conditioner to be turned on at 9:50 PM if they are not home and it\'s cold outside. First, I need to determine if the user will be late arriving home at that time.",\n    "Arguments": "["school", "home", "driving"]",\n    "Target_tool": "PathPlanning"\n}
Observation: 从用户的家到目的地驾车所需时间为：26.35分钟
DeviceControler: {\n    "Action_type": "CallTools",\n    "Thought": "The user has previously requested that if they are not home by 9:50 PM and it is cold outside, the bedroom air conditioner should be turned on. Since the user\'s travel time from school to home is about 26.35 minutes, I need to calculate the actual time of arrival based on their departure time and compare it with 9:50 PM. I also need to check the weather conditions at the user\'s home to determine if it is indeed cold.",\n    "Arguments": "",\n    "Target_tool": "Time"\n}
Observation: 当前时间是：2025-01-31 21:47:41
DeviceControler: {\n    "Action_type": "CallTools",\n    "Thought": "To determine if it is cold outside, I need to call the WeatherInformation tool to get the current temperature at the user\'s home location.",\n    "Arguments": "",\n    "Target_tool": "WeatherInformation"\n}
Observation: 用户家所在区域的气象信息是<省略的具体气象信息>
DeviceControler: {\n    "Action_type": "SeekHelp",\n    "Thought": "Based on the time, traffic, and temperature information I have gathered, I can determine that, according to the user's request, the air conditioner needs to be turned on in half an hour. Since the command is not to be executed immediately, I need to seek help from other agents.",\n    "Say_to_agent": "半小时后打开卧室的空调。"\n}

# Important Notes
1. Only one action per response. If multiple inputs are needed, request them incrementally.
2. Only modify properties with 'write' access. Inform the user if a property is read-only.
3. Carefully analyze every premise in the user's request and ensure that all premises are sufficiently supported by evidence before issuing a command. Never assume any information.
4. Always call the tool Time if you want to check the current time.
5. Sensor data intelligently reflects indoor environmental data but cannot represent weather conditions.
6. You must **only returns a json string** in the format of the examples above.
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
        self.tool_agent = [weather_tool_agent(), map_tool_agent()]
        self.time = time_tool_agent()
        self.tool_list = self.tool_agent_to_tool_list()
        self.tool_dict = self.tool_agent_to_tool_dict()

    def parse_output(self, output: str) -> dict:
        """将LLM的输出转换为JSON字符串."""
        match = re.search(r"```json\s*(.*?)\s*```", output, re.DOTALL)
        if match:
            return json.loads(match.group(1).strip())
        return json.loads(output.strip())

    async def run(self, history_msg: list[Message], user_input: Message) -> Message:
        _logger.info(f"DeviceControler run: {user_input}")
        user_request = user_input.content
        if not self.llm.sysmsg_added:
            self.llm.add_system_msg(SYSTEM_MESSAGE_2)

        all_context = CONFIG.hass_data["all_context"]
        sensor_data = CONFIG.hass_data["all_sensor_data"]

        curr_time = await self.time.run(None)
        if user_input.attachment is not None:
            dep = f"current time:{curr_time}\n{user_input.attachment.content}"
        else:
            dep = f"current time:{curr_time}\n"

        if user_input.role == "Tool":
            self.llm.add_user_msg(TOOL_MESSAGE.format(tool_return=user_request))
        else:
            self.llm.add_user_msg(
                USER_MESSAGE.format(
                    user_request=user_request,
                    device_list=all_context,
                    tool_list=self.tool_list,
                    sensor_data=sensor_data,
                    dependency_task_info=dep,
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
                    # 调用tool
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
                    content=dep,
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
