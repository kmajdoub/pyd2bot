from collections import defaultdict
from typing import Set, List
from pyd2bot.farmPaths.AbstractFarmPath import AbstractFarmPath
from pyd2bot.farmPaths.RandomAreaFarmPath import NoTransitionFound
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.astar.AStar import AStar
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import Edge
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import WorldGraph
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from time import time
from random import choice

class CyclicFarmPath(AbstractFarmPath):
    def __init__(self, name: str, mapIds: List[int]) -> None:
        super().__init__()
        self.name = name
        self._mapIds = mapIds
        self.startVertex = WorldGraph().getVertex(mapIds[0], 1)
        self._next_edges = defaultdict(list)  # vertex -> list of possible next edges
        self._complete_path: List[Edge] = []
        self._vertex_history = defaultdict(float)  # vertex -> last visit timestamp
        
    @property
    def mapIds(self) -> List[int]:
        return self._mapIds
    
    def init(self):
        Logger().debug(f"Running cyclic farm path with mapIds : {self.mapIds}")
        self._build_complete_path()
        # Add this to init() to debug the path
        Logger().debug(f"Path sequence: {[edge.src.mapId for edge in self._complete_path]}")
        Logger().debug(f"Total unique maps in path: {len(set(edge.src.mapId for edge in self._complete_path))}")

    def _build_complete_path(self):
        """Builds the complete cyclic path connecting all maps."""
        self._complete_path = []
        self._next_edges.clear()
        self._vertices.clear()
        
        # Build path segments between consecutive maps
        for i in range(len(self._mapIds)):
            current_map_id = self._mapIds[i]
            next_map_id = self._mapIds[(i + 1) % len(self._mapIds)]
            
            src_vertex = WorldGraph().getVertex(current_map_id, 1)
            dst_vertex = WorldGraph().getVertex(next_map_id, 1)
            
            if not src_vertex or not dst_vertex:
                raise Exception(f"Could not find vertices for maps {current_map_id} -> {next_map_id}")
                
            path_segment = AStar().search(src_vertex, dst_vertex)
            if not path_segment:
                raise Exception(f"No path found between maps {current_map_id} -> {next_map_id}")
                
            self._complete_path.extend(path_segment)
            
            # Build the next_edges mapping from path segment
            for edge in path_segment:
                self._next_edges[edge.src].append(edge)
                self._vertices.add(edge.src)
                self._vertices.add(edge.dst)
            
        # Add final connection to make it cyclic
        if self._complete_path:
            last_vertex = self._complete_path[-1].dst
            first_vertex = self._complete_path[0].src
            if last_vertex != first_vertex:
                closing_path = AStar().search(last_vertex, first_vertex)
                if closing_path:
                    self._complete_path.extend(closing_path)
                    for edge in closing_path:
                        self._next_edges[edge.src].append(edge)
                        self._vertices.add(edge.src)
                        self._vertices.add(edge.dst)

    def __next__(self, forbiddenEdges=None) -> Edge:
        """Get next edge in cycle."""
        return self.getNextEdge(forbiddenEdges)

    def getNextEdge(self, forbiddenEdges=None, onlyNonRecent=False) -> Edge:
        """Get the next edge to follow in the path."""
        curr_vertex = PlayedCharacterManager().currVertex
        
        if not self._next_edges[curr_vertex]:
            raise NoTransitionFound("Current position not in path and could not find way back!")
            
        possible_edges = self._next_edges[curr_vertex]
        recently_visited = {v for v, t in self._vertex_history.items() if time() - t < 60}
        
        non_recent_edges = [e for e in possible_edges if e.dst not in recently_visited]
        chosen_edge = choice(non_recent_edges) if non_recent_edges else choice(possible_edges)
        
        self._vertex_history[curr_vertex] = time()
        return chosen_edge

    @property
    def vertices(self) -> Set[Vertex]:
        """Get all vertices in the path."""
        if not self._vertices:
            self._build_complete_path()
        return self._vertices