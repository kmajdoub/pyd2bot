import collections
import random
from typing import Iterator

from pyd2bot.thriftServer.pyd2botService.ttypes import Path
from pydofus2.com.ankamagames.dofus.datacenter.world.SubArea import SubArea
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.astar.AStar import AStar
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Transition import Transition
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import WorldGraph
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldPathFinder import WorldPathFinder
from pyd2bot.models.farmPaths.AbstractFarmPath import AbstractFarmPath


class RandomSubAreaFarmPath(AbstractFarmPath):
    def __init__(
        self,
        name: str,
        startVertex: Vertex,
        onlyDirections: bool = True,
    ) -> None:
        self.name = name
        self.startVertex = startVertex
        self.subArea = SubArea.getSubAreaByMapId(startVertex.mapId)
        self._currentVertex = None
        self._verticies = list[Vertex]()
        self.onlyDirections = onlyDirections

    def __next__(self) -> Transition:
        outgoingEdges = WorldGraph().getOutgoingEdgesFromVertex(self.currentVertex)
        transitions = []
        for edge in outgoingEdges:
            if edge.dst.mapId in self.subArea.mapIds:
                if AStar.hasValidTransition(edge):
                    for tr in edge.transitions:
                        if not self.onlyDirections or tr.direction != -1:
                            transitions.append(tr)
        return random.choice(transitions)

    def currNeighbors(self) -> Iterator[Vertex]:
        return self.neighbors(self.currentVertex)

    def neighbors(self, vertex: Vertex) -> Iterator[Vertex]:
        outgoingEdges = WorldGraph().getOutgoingEdgesFromVertex(vertex)
        for edge in outgoingEdges:
            if edge.dst.mapId in self.subArea.mapIds:
                found = False
                for tr in edge.transitions:
                    if tr.direction != -1:
                        found = True
                        break
                if found:
                    yield edge.dst

    @property
    def verticies(self):
        if self._verticies:
            return self._verticies
        queue = collections.deque([self.startVertex])
        self._verticies = set([self.startVertex])
        while queue:
            curr = queue.popleft()
            for v in self.neighbors(curr):
                if v not in self._verticies:
                    queue.append(v)
                    self._verticies.add(v)
        return self._verticies

    def __iter__(self) -> Iterator[Vertex]:
        for it in self.verticies:
            yield it

    def __in__(self, vertex: Vertex) -> bool:
        return vertex in self.verticies

    def to_json(self) -> dict:
        return {
            "type": self.__class__.__name__,
            "name": self.name,
            "subAreaId": self.subArea.id,
            "startVertex": {
                "mapId": self.startVertex.mapId,
                "mapRpZone": self.startVertex.zoneId,
            },
        }

    @classmethod
    def from_thriftObj(cls, path: Path) -> "RandomSubAreaFarmPath":
        startVertex = WorldGraph().getVertex(path.startVertex.mapId, path.startVertex.zoneId)
        if startVertex is None:
            raise ValueError("Could not find start vertex from startVertex : " + str(path.startVertex))
        return cls(path.id, startVertex)
