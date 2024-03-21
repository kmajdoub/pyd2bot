from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.farm.ResourceFarm import ResourceFarm
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class MultiplePathsResourceFarm(AbstractBehavior):

    def __init__(self, timeout=None) -> None:
        self.timeout = timeout
        super().__init__()

    def run(self) -> bool:
        self.pathsList = BotConfig().pathsList
        self.iterPathsList = iter(self.pathsList)
        Logger().info(f"Starting multiple paths resource farm with {len(self.pathsList)} paths with timeout {self.timeout // 60} minutes")
        self.startNextPath(None, None)

    def startNextPath(self, code, err):
        Logger().info(f"Starting next path")
        try:
            self.currentPath = next(self.iterPathsList)
        except StopIteration:
            self.iterPathsList = iter(self.pathsList)
            self.currentPath = next(self.iterPathsList)
        BotConfig().path = self.currentPath
        ResourceFarm(self.timeout).start(callback=self.startNextPath)
