from pyd2bot.farmPaths.AbstractFarmPath import AbstractFarmPath
from pyd2bot.farmPaths.RandomAreaFarmPath import NoTransitionFound
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import Edge
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import WorldGraph

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
        pass

    def getNextEdge(self, forbiddenEdges=None, onlyNonRecent=False) -> Edge:
        """Get the edge leading to the next map in the cycle."""
        if forbiddenEdges is None:
            forbiddenEdges = []
            
        # Get next map ID in cycle
        next_index = (self._current_map_index + 1) % len(self._mapIds)
        next_map_id = self._mapIds[next_index]
        
        # Get destination vertex
        dest_vertex = WorldGraph().getVertex(next_map_id, 1)
        if not dest_vertex:
            raise NoTransitionFound("Could not find vertex for map " + str(next_map_id))
            
        # Get edge between current and destination vertex
        edge = WorldGraph().getEdge(self.currentVertex, dest_vertex)
        if not edge or edge in forbiddenEdges or not self.hasValidTransition(edge):
            raise NoTransitionFound("No valid edge found to next map in cycle")
            
        # Update current map index
        self._current_map_index = next_index
        return edge

    def __next__(self, forbiddenEdges=None) -> Edge:
        """Get next edge in cycle."""
        return self.getNextEdge(forbiddenEdges)
