import random
import time
from typing import Iterator
from pyd2bot.farmPaths.AbstractFarmPath import AbstractFarmPath
from pyd2bot.farmPaths.RandomAreaFarmPath import NoTransitionFound
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import \
    Edge
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import \
    Vertex
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import \
    WorldGraph
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class CustomRandomFarmPath(AbstractFarmPath):
    def __init__(
        self,
        name: str,
        mapIds: list[int]
    ) -> None:
        super().__init__()
        self.name = name
        self._mapIds = mapIds
        self.startVertex = WorldGraph().getVertex(self._mapIds[0], 1)

    @property
    def mapIds(self) -> list[int]:
        return self._mapIds
    
    def init(self):
        Logger().info(f"CustomRandomFarmPath {self.name} initialized with {len(self.verticies)} verticies")

    def __next__(self, forbidenEdges=None) -> Edge:
        outgoingEdges = list(self.outgoingEdges(onlyNonRecentVisited=False))
        if forbidenEdges is None:
            forbidenEdges = []
        outgoingEdges = [e for e in outgoingEdges if e not in forbidenEdges]
        if not outgoingEdges:
            raise NoTransitionFound()
        edge = random.choice(outgoingEdges)
        return edge

    def currNeighbors(self) -> Iterator[Vertex]:
        return self.outgoingEdges(self.currentVertex)
    
    def outgoingEdges(self, vertex=None, onlyNonRecentVisited=False) -> Iterator[Edge]:
        if vertex is None:
            vertex = self.currentVertex
        outgoingEdges = WorldGraph().getOutgoingEdgesFromVertex(vertex)
        ret = []
        for edge in outgoingEdges:
            if edge.dst.mapId in self.mapIds:
                if self.hasValidTransition(edge):
                    if onlyNonRecentVisited:
                        if edge.dst in self._lastVisited:
                            if time.perf_counter() - self._lastVisited[edge.dst] > 60 * 60:
                                ret.append(edge)
                        else:
                            ret.append(edge)
                    else:
                        ret.append(edge)
        return ret
    
    def getNextEdge(self, forbidenEdges=None, onlyNonRecent=False) -> Edge:
        outgoingEdges = list(self.outgoingEdges(onlyNonRecentVisited=onlyNonRecent))
        if forbidenEdges is None:
            forbidenEdges = []
        outgoingEdges = [e for e in outgoingEdges if e not in forbidenEdges]
        if not outgoingEdges:
            raise NoTransitionFound()
        edge = random.choice(outgoingEdges)
        return edge
    