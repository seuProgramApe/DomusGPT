from .actions.action import Action
from .message import Message
from .utils.logs import _logger
from .llm import LLM
import asyncio
import json

SYSTEM_MESSAGE = """
# Role
你是智能家居系统中的Manager， 你的工作是将用户提出的复杂请求分解为简单的可执行子任务，并交付专门用来执行任务的其他agent执行。

# Input
用户需求（request）

# Solution
你需要将用户需求分解为若干子任务，并解析它们之间的依赖关系。对于每个子任务的内容，你只需要重复用户的这部分自然语言，而不需要任何程度的归纳总结。
你需要按照以下规则分解任务：
1. 子任务的的结构为({C1, C2, C3, ... , Ci}, A)，其中Ci被称为限制，A被称为动作。子任务的限制可以为空集。
2. 子任务的**限制**是子任务的前提条件，例如：环境限制（由包括室内传感器可以获取的数据，例如室温、湿度、光照等，和其他环境条件：例如天气情况、交通情况、时间因素等）。
3. 子任务的**动作**仅属于且必须属于以下三类之一：
    1. 设备控制（Device Control）：操控屋内的智能家居设备，用户可以不明确地指定具体操作（例如“优化屋内的灯光控制。”）
    2. TAP（trigger action program）生成（TAP generation）：针对用户提出的生成自动化脚本请求，生成对应的自动化
    3. 其他信息答复（General Q&A）：**当且仅当用户明确提出需要agent回复**时，回复用户有关室内的环境数据（例如室内的各种传感器可以获取的数据）或其他环境数据（例如天气情况、交通情况）或其他百科知识（例如询问某种事物、某位名人的信息）的问题。
你需要仔细分析用户请求 ，并输出任务分解的结果。
在这一过程中，你需要注意到别遵守以下规则：
如果某个子任务的部分内容是等待某个环境条件发生变化后，进行的设备控制操作（例如：当……时/以后，控制某设备），而不是仅仅基于对当前环境条件的判断而决定是否对设备进行**即时控制**（例如：如果……则控制某设备），那么这部分内容是一个完整的**TAP生成**动作，而不是限制和设备控制动作的集合。
但若某个子任务的限制是对当前环境条件的判断，或者是对未来某个事件发生时的时间、环境情况的预测，**动作**是对某个设备的**即时控制**，那么该子任务是一个**设备控制**任务。
所有的General Q&A任务应该被压缩到一个子任务中。

特别注意：
1. 当某个任务的**限制**中包含**时延前提**（例如前提为：空调打开15分钟后、半小时后等），即使这个任务的动作是**设备控制**，也应该被归类为TAP生成。
2. 当多个子任务的**动作**都属于**设备控制**，而**限制**完全相同时，应该被压缩为一个子任务。

# Output
你将先确定思维链（COT），在这部分内容中，你需要阐述你是如何逐一分解出子任务并确定每个任务的类型。接着，你将确定分解后的结果。这两部分内容必须整合在一个**JSON数组**中一起输出。
**JSON数组**的格式如下：
[
    { "COT": <COT>},
    { "id": <id>,
      "type": <type>(Device Control or TAP generation or General Q&A),
      "content": <content>,
      "dependency": [<此任务依赖的其他子任务的id>]
     },
     ...
]
你只需要输出JSON数组即可。

# Examples
Example1:
User Input: 如果现在交通状况良好，而且外面气温很低的话，帮我打开空调。打开空调十五分钟后打开加湿器。
Assistant:
[
    { "COT": "用户需求中包含两个子任务：1. 如果现在交通状况良好，而且外面气温很低的话，帮用户打开空调。2. 打开空调十五分钟后打开加湿器。第一个子任务的限制是：如果现在交通状况良好，而且外面气温很低的话。这是基于对当前环境条件的判断而决定是否对设备进行即时控制，因此是设备控制任务。第二个子任务的限制是：打开空调十五分钟后。这是时延前提。因此该子任务一个TAP生成任务。"},
    { "id": 1,
      "type": Device Control,
      "content": 如果交通状况良好，且外面气温很低，打开空调,
      "dependency": [],
     }，
    { "id": 2,
      "type":TAP generation,
      "content": 打开空调十五分钟后打开加湿器,
      "dependency": [1]
     }
]

Example2:
User Input: 如果我现在开车从学校出发，七点半之前不能到家，帮我打开空调。
Assistant:
[
    { "COT": "用户需求可以总结为：如果用户现在开车从学校出发，七点半之前不能到家，帮用户打开空调。该任务的限制是：用户现在开车从学校出发，七点半之前不能到家。这是基于对当前环境条件的判断而决定是否对设备进行即时控制，因此是设备控制任务。"},
    { "id": 1,
      "type": Device Control,
      "content": 如果用户现在开车从学校出发，七点半之前不能到家，帮用户打开空调,
      "dependency": [],
     }
]
"""

USER_MESSAGE = """user_request: {user_request}"""


class Router(Action):
    def __init__(self, name="Manager", context=None):
        super().__init__(name, context)
        self.llm = LLM()

    async def run(self, user_input: Message) -> list:
        user_request = user_input.content
        self.llm.add_system_msg(SYSTEM_MESSAGE)
        self.llm.add_user_msg(USER_MESSAGE.format(user_request=user_request))
        loop = asyncio.get_running_loop()
        rsp = await loop.run_in_executor(
            None, self.llm.chat_completion_text_v1, self.llm.history
        )
        _logger.info(f"Router response: {rsp}")
        self.llm.reset()

        rsp_list = self.parse_output(rsp)
        print("分解后任务列表是: " + rsp)
        return rsp_list

    def parse_output(self, output: str) -> dict:
        """将LLM的输出转换为JSON字符串."""
        # TODO error handling
        if output.startswith("```json"):
            output = output[7:]
            output = output[:-3]
            return json.loads(output.strip())
        if output.startswith("```"):
            output = output[3:]
            output = output[:-3]
            return json.loads(output.strip())
        output = output.replace("}{", "},{")
        return json.loads(output.strip())

    def reset(self):
        self.llm.reset()
        _logger.info(f"{self.name} reset.")
