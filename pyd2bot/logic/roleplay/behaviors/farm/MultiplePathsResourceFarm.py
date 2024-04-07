import math
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.farm.ResourceFarm import ResourceFarm
from pyd2bot.farmPaths.AbstractFarmPath import AbstractFarmPath
from pyd2bot.data.models import JobFilter
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class MultiplePathsResourceFarm(AbstractBehavior):
    default_ncovers = 3
    
    def __init__(self, pathsList: list[AbstractFarmPath], jobFilter: JobFilter, num_of_covers: int=None) -> None:
        for path in pathsList:
            if not isinstance(path, AbstractFarmPath):
                raise ValueError(f"Invalid path type {type(path)}")
        self.jobFilter = jobFilter
        self.num_of_covers = num_of_covers
        self.pathsList = pathsList
        self.forbidden_paths = []
        if not self.num_of_covers:
            self.num_of_covers = self.default_ncovers
        super().__init__()

    def run(self) -> bool:
        self.iterPathsList = iter(self.pathsList)
        Logger().info(f"Starting multiple paths resource farm with {len(self.pathsList)} paths.")
        self.startNextPath(None, None)

    def coverTimeEstimate(self, path: AbstractFarmPath):
        n = len(path.verticies)
        return n * n * math.log(n) * 10 # 10 seconds per vertex
    
    def startNextPath(self, code, err):
        if err:
            Logger().debug(f"Error[{code}] during the farm path : {err}")
            self.forbidden_paths.append(self.currentPath)
        Logger().info(f"Starting next path")
        try:
            self.currentPath = next(self.iterPathsList)
        except StopIteration:
            non_forbidden_paths = [p for p in self.pathsList if p not in self.forbidden_paths]
            if not non_forbidden_paths:
                return self.finish(1, "All paths are forbidden")
            self.iterPathsList = iter(non_forbidden_paths)
            self.currentPath = next(self.iterPathsList)
        timeout = self.num_of_covers * self.coverTimeEstimate(self.currentPath)
        ResourceFarm(self.currentPath, self.jobFilter, timeout).start(callback=self.startNextPath)
