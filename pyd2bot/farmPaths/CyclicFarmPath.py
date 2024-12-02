from typing import Set
from pyd2bot.farmPaths.AbstractFarmPath import AbstractFarmPath
from pyd2bot.farmPaths.RandomAreaFarmPath import NoTransitionFound
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import Edge
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import WorldGraph
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

class CyclicFarmPath(AbstractFarmPath):
    def __init__(self, name: str, mapIds: list[int]) -> None:
        super().__init__()
        self.name = name
        self._mapIds = mapIds
        self.startVertex = WorldGraph().getVertex(mapIds[0], 1)
        self._current_map_index = 0

    @property
    def mapIds(self) -> list[int]:
        return self._mapIds
    
    def init(self):
        Logger().debug(f"Running cyclic farm path with mapIds : {self.mapIds}")

    def __next__(self, forbiddenEdges=None) -> Edge:
        """Get next edge in cycle."""
        return self.getNextEdge(forbiddenEdges)

    def getNextVertex(self) -> Vertex:
        """Get the next vertex in the cycle."""
        # Get next map ID in cycle
        next_index = (self._current_map_index + 1) % len(self._mapIds)
        next_map_id = self._mapIds[next_index]
        
        # Get destination vertex
        next_vertex = WorldGraph().getVertex(next_map_id, 1)
        if not next_vertex:
            raise NoTransitionFound(f"Could not find vertex for map {next_map_id}")
            
        # Update current map index
        self._current_map_index = next_index
        return next_vertex

    @property
    def vertices(self) -> Set['Vertex']:
        if not self._vertices:
            self._vertices = [WorldGraph().getVertex(mapId, 1) for mapId in self._mapIds]
        return self._vertices

    def __in__(self, vertex: 'Vertex') -> bool:
        return vertex.mapId in self.mapIds