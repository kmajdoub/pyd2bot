from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.farm.ResourceFarm import ResourceFarm
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class MultiplePathsResourceFarm(AbstractBehavior):

    def __init__(self) -> None:
        self.default_minutes_per_path = 5
        self.forbiden_paths = []
        super().__init__()

    def run(self) -> bool:
        self.pathsList = BotConfig().pathsList
        self.iterPathsList = iter(self.pathsList)
        if BotConfig().session.minute_per_path:
            self.timeout = BotConfig().session.minute_per_path * 60
        else:
            self.timeout = self.default_minutes_per_path * 60
        Logger().info(f"Starting multiple paths resource farm with {len(self.pathsList)} paths with timeout {self.timeout // 60} minutes")
        self.startNextPath(None, None)

    def startNextPath(self, code, err):
        if err:
            Logger().debug(f"Error[{code}] during the farm path : {err}")
            self.forbiden_paths.append(self.currentPath)
        Logger().info(f"Starting next path")
        try:
            self.currentPath = next(self.iterPathsList)
        except StopIteration:
            non_forbiden_paths = [p for p in self.pathsList if p not in self.forbiden_paths]
            if not non_forbiden_paths:
                return self.finish(1, "All paths are forbiden")
            self.iterPathsList = iter([p for p in self.pathsList if p not in self.forbiden_paths])
            self.currentPath = next(self.iterPathsList)
        BotConfig().curr_path = self.currentPath
        ResourceFarm(self.timeout).start(callback=self.startNextPath)
