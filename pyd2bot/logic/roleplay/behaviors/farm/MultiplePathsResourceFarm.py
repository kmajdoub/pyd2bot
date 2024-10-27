import math
from typing import List
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.farm.ResourceFarm import ResourceFarm
from pyd2bot.farmPaths.AbstractFarmPath import AbstractFarmPath
from pyd2bot.data.models import JobFilter
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class MultiplePathsResourceFarm(AbstractBehavior):
    default_ncovers = 3
    
    def __init__(self, pathsList: list[AbstractFarmPath], jobFilters: List[JobFilter], num_of_covers: int=None) -> None:
        for path in pathsList:
            if not isinstance(path, AbstractFarmPath):
                raise ValueError(f"Invalid path type {type(path)}")
        self.jobFilters = jobFilters
        self.num_of_covers = num_of_covers
        self.pathsList = pathsList
        self.forbidden_paths = []
        if not self.num_of_covers:
            self.num_of_covers = self.default_ncovers
        self._current_running_behavior = None
        self._wants_stop = False
        super().__init__()

    def stop(self):
        self._wants_stop = True
        if self._current_running_behavior:
            self._current_running_behavior.stop()
        
    def run(self) -> bool:
        self.iterPathsList = iter(self.pathsList)
        Logger().info(f"Starting multiple paths resource farm with {len(self.pathsList)} paths.")
        self.startNextPath(None, None)

    def coverTimeEstimate(self, path: AbstractFarmPath):
        n = len(path.vertices)
        return n * n * math.log(n) * 10 # 10 seconds per vertex
    
    def startNextPath(self, code, err):
        if self._wants_stop:
            return self.finish(self.STOPPED, None)

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
        self._current_running_behavior = ResourceFarm(self.currentPath, self.jobFilters, timeout)
        self._current_running_behavior.start(callback=self.startNextPath)
