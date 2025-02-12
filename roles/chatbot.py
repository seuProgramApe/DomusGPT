from ..roles.role import Role
from ..actions.chat import Chat


class Chatbot(Role):
    def __init__(
        self,
        name="",
        profile="Chatbot",
        goal="Friendly chat with users about things not related to controiing devices or generating TAPs",
        **kwargs,
    ):
        super().__init__(name=name, profile=profile, goal=goal, **kwargs)
        self._init_actions([Chat])
        self._watch(["UserInput", "Test"])
