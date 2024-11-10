import math
import random
from typing import List
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.farm.ResourceFarm import ResourceFarm
from pyd2bot.farmPaths.AbstractFarmPath import AbstractFarmPath
from pyd2bot.data.models import JobFilter
from pyd2bot.logic.roleplay.behaviors.updates.CollectStats import CollectStats
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

class MultiplePathsResourceFarm(AbstractBehavior):
    default_ncovers = 3

    # Constants for timeout calculation
    BASE_TIMEOUT = 5 * 60       # 5 minutes base timeout
    MAX_TIMEOUT = 60 * 60       # 60 minutes maximum timeout
    VERTEX_TIME = 10            # 10 seconds per vertex for resource interaction
    MIN_TIMEOUT = 5 * 60        # 10 minutes minimum timeout

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

    def calculate_timeout(self, path: AbstractFarmPath) -> float:
        """
        Calculate timeout based on grid properties.
        For a grid, random walk coverage time is O(n log²n) where n is number of vertices.
        Returns timeout in seconds.
        """
        n = path.get_vertices_count()
        m = path.get_edge_count()
        
        if n <= 1:
            return self.MIN_TIMEOUT
            
        # Calculate average degree (in a perfect grid it would be 4)
        avg_degree = (2 * m) / n  # multiply by 2 because edges are counted once but connect two vertices
        
        # For a grid with missing connections:
        # - Perfect grid: avg_degree = 4
        # - Our grid: avg_degree < 4 means missing connections
        grid_sparsity = avg_degree / 4  # will be 1.0 for perfect grid, less for missing connections
        
        # Base exploration time for a grid with missing connections
        # n * log²(n) is the theoretical bound for a perfect grid
        # We add penalty for missing connections
        log_factor = math.log(n) * math.log(n)
        exploration_multiplier = 1 + max(0, (1 - grid_sparsity) * 2)  # More penalty for more missing connections
        exploration_time = n * log_factor * exploration_multiplier
        
        # Add time for resource gathering
        interaction_time = n * self.VERTEX_TIME
        
        # Calculate total time needed for one cover
        time_per_cover = exploration_time + interaction_time
        
        # Total timeout with all covers
        total_timeout = self.BASE_TIMEOUT + (time_per_cover * self.num_of_covers)
        
        # Bound the timeout
        timeout = min(max(self.MIN_TIMEOUT, total_timeout), self.MAX_TIMEOUT)
        
        Logger().debug(f"""Timeout calculation for grid path {path.name}:
            Vertices: {n}
            Edges: {m}
            Average degree: {avg_degree:.2f}/4.0
            Grid sparsity: {grid_sparsity:.2f}
            Exploration multiplier: {exploration_multiplier:.2f}x
            Base exploration: {exploration_time:.1f}s
            Interaction time: {interaction_time:.1f}s
            Per cover: {time_per_cover:.1f}s
            Total timeout: {timeout:.1f}s ({timeout/60:.1f}min)""")

        return timeout

    def stop(self):
        self._wants_stop = True
        if self._current_running_behavior:
            self._current_running_behavior.stop()

    def run(self) -> bool:
        Logger().info(f"Starting multiple paths resource farm with {len(self.pathsList)} paths in random mode.")
        self.startNextPath(None, None)

    def coverTimeEstimate(self, path: AbstractFarmPath):
        n = len(path.vertices)
        return n * math.log(n) * math.log(n) * 5

    def startNextPath(self, code, err):
        if self._wants_stop:
            return self.finish(self.STOPPED, None)

        if err:
            Logger().debug(f"Error[{code}] during the farm path : {err}")
            self.forbidden_paths.append(self.currentPath)

        Logger().info(f"Starting next path")
        
        # Get available paths
        available_paths = [p for p in self.pathsList if p not in self.forbidden_paths]
        if not available_paths:
            return self.finish(1, "All paths are forbidden")
            
        # Randomly select next path
        self.currentPath = random.choice(available_paths)
        
        # Calculate smart timeout based on graph properties
        timeout = self.calculate_timeout(self.currentPath)

        self._current_running_behavior = ResourceFarm(self.currentPath, self.jobFilters, timeout)
        self._current_running_behavior.start(callback=self.startNextPath)
