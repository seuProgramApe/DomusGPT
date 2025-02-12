from abc import ABC, abstractmethod
from ..utils.logs import _logger
from ..tool_agent import tool_agent


class Action(ABC):
    def __init__(self, name="", context=None):
        _logger.debug("Action init")
        _logger.debug(f"Action name: {name}")
        self.name: str = name
        self.context = context
        self.prefix = ""
        self.profile = ""
        self.desc = ""
        self.content = ""
        self.tool_agent: list[tool_agent] = ""

    def set_prefix(self, prefix, profile):
        """Set prefix for later usage."""
        self.prefix = prefix
        self.profile = profile

    def __str__(self):
        return self.__class__.__name__

    def __repr__(self):
        return self.__str__()

    @abstractmethod
    async def run(self, *args, **kwargs):
        """Run action."""
        raise NotImplementedError("The run method should be implemented in a subclass.")

    @abstractmethod
    def reset():
        """Reset action."""
        raise NotImplementedError(
            "The reset method should be implemented in a subclass."
        )

    def tool_agent_to_tool_list(self) -> list:
        """将action中的tool_agent列表转换为llm可识别的tool_list."""
        return [
            {"name": tool.profile, "function": tool.function, "argument": tool.argument}
            for tool in self.tool_agent
        ]

    def tool_agent_to_tool_dict(self) -> dict[str:tool_agent]:
        """将action中的tool_agent列表转换为可用名称获取tool实例的字典."""
        todict = {}
        for tool in self.tool_agent:
            todict[tool.profile] = tool
        return todict
