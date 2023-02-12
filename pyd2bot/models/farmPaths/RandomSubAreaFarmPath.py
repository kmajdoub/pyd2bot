import collections
import random
import time
from typing import Iterator, Tuple

from pyd2bot.thriftServer.pyd2botService.ttypes import Path
from pydofus2.com.ankamagames.dofus.datacenter.world.SubArea import SubArea
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.astar.AStar import AStar
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import Edge
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Transition import Transition
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import WorldGraph
from pyd2bot.models.farmPaths.AbstractFarmPath import AbstractFarmPath
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.pathfinding.Pathfinding import Pathfinding

from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint


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
        self._recent_visited = list[Tuple['Vertex', float]]()

    def recentVisitedVerticies(self):
        self._recent_visited = [(_, time_added) for (_, time_added) in self._recent_visited if (time.time() - time_added) < 30]
        return [v for v, _ in self._recent_visited]
    
    def __next__(self) -> Transition:
        from pydofus2.com.ankamagames.atouin.utils.DataMapProvider import DataMapProvider
        outgoingEdges = WorldGraph().getOutgoingEdgesFromVertex(self.currentVertex)
        transitions = []
        for edge in outgoingEdges:
            if edge.dst.mapId in self.subArea.mapIds:
                if AStar.hasValidTransition(edge):
                    for tr in edge.transitions:
                        if not self.onlyDirections or tr.direction != -1:
                            if tr.cell:
                                currMP = PlayedCharacterManager().entity.position
                                candidate = MapPoint.fromCellId(tr.cell)
                                movePath = Pathfinding().findPath(DataMapProvider(), currMP, candidate)
                                if movePath.end == candidate:
                                    transitions.append((edge, tr))
                            else:
                                transitions.append((edge, tr))
        notrecent = [tr for edge, tr in transitions if edge.dst not in self.recentVisitedVerticies()]
        if notrecent:
            tr = random.choice(notrecent)
        else:
            _, tr = random.choice(transitions)
        self._recent_visited.append((self.currentVertex, time.time()))
        return tr

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
