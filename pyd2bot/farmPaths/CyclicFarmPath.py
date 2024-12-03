from typing import Iterator, Set
from pyd2bot.farmPaths.AbstractFarmPath import AbstractFarmPath
from pyd2bot.farmPaths.RandomAreaFarmPath import NoTransitionFound
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.astar.AStar import AStar
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
        self._vertices = None
        self._next_edge = {}

    @property
    def mapIds(self) -> list[int]:
        return self._mapIds
    
    def init(self):
        Logger().debug(f"Running cyclic farm path with mapIds : {self.mapIds}")

    def __next__(self, forbiddenEdges=None) -> Edge:
        """Get next edge in cycle."""
        return self.getNextEdge(forbiddenEdges)

    def getNextEdge(self, forbiddenEdges=None, onlyNonRecent=False) -> Edge:
        # Ensure path mapping is computed
        if not self._next_edge:
            self.vertices
            
        # Get current position and find next edge
        curr_vertex = PlayedCharacterManager().currVertex
        next_edge = self._next_edge.get(curr_vertex)
        
        if next_edge is None:
            raise NoTransitionFound("Current position not in path!")

        return next_edge

    @property
    def vertices(self) -> Set['Vertex']:
        if not self._vertices:
            # Initialize set to store all vertices
            self._vertices = set()
            self._next_edge.clear()
            
            # Add all terminal vertices first
            for map_id in self._mapIds:
                vertex = WorldGraph().getVertex(map_id, 1)
                if vertex:
                    self._vertices.add(vertex)
            
            # Find paths between consecutive terminal points
            for i in range(len(self._mapIds)):
                # Get current and next map indices
                current_map_id = self._mapIds[i]
                next_map_id = self._mapIds[(i + 1) % len(self._mapIds)]
                
                # Get source and destination vertices
                src_vertex = WorldGraph().getVertex(current_map_id, 1)
                dst_vertex = WorldGraph().getVertex(next_map_id, 1)
                
                if src_vertex and dst_vertex:
                    path_edges = AStar().search(src_vertex, dst_vertex)
                    if path_edges is None:
                        raise Exception("Invalid cyclic path given, found two vertices not in same connected component!")
                    
                    for edge in path_edges:
                        self._next_edge[edge.src] = edge
                        self._vertices.add(edge.src)
                        self._vertices.add(edge.dst)

        return self._vertices
