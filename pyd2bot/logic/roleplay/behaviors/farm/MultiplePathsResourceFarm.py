import math
from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.farm.ResourceFarm import ResourceFarm
from pyd2bot.models.farmPaths.AbstractFarmPath import AbstractFarmPath
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class MultiplePathsResourceFarm(AbstractBehavior):

    def __init__(self) -> None:
        self.default_ncovers = 3
        self.forbiden_paths = []
        super().__init__()

    def run(self) -> bool:
        self.pathsList = BotConfig().pathsList
        self.iterPathsList = iter(self.pathsList)
        if not BotConfig().session.number_of_covers:
            BotConfig().session.number_of_covers = self.default_ncovers
        Logger().info(f"Starting multiple paths resource farm with {len(self.pathsList)} paths.")
        self.startNextPath(None, None)

    def coverTimeEstimate(self, path: AbstractFarmPath):
        n = len(path.verticies)
        return n * n * math.log(n) * 10 # 10 seconds per vertex
    
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
        timeout = BotConfig().session.number_of_covers * self.coverTimeEstimate(self.currentPath)
        ResourceFarm(timeout).start(callback=self.startNextPath)
