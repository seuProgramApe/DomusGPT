from ..roles.role import Role
from ..actions.generate_tap import GenerateTAP


class TapGenerator(Role):
    def __init__(
        self,
        name="",
        profile="TAPGenerator",
        goal="Generate TAP based on user requests",
        **kwargs,
    ):
        super().__init__(name=name, profile=profile, goal=goal, **kwargs)
        self._init_actions(
            [GenerateTAP]
        )  # 李安：决定了TapGenerator角色只有一个action，即GenerateTAP
        self._watch(["UserInput"])
