import random
from time import perf_counter
from typing import Iterator, Set

from pyd2bot.farmPaths.AbstractFarmPath import AbstractFarmPath
from pydofus2.com.ankamagames.dofus.datacenter.world.MapPosition import \
    MapPosition
from pydofus2.com.ankamagames.dofus.datacenter.world.SubArea import SubArea
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.astar.AStar import \
    AStar
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import \
    Edge
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.TransitionTypeEnum import \
    TransitionTypeEnum
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import \
    Vertex
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import \
    WorldGraph
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class NoTransitionFound(Exception):
    pass
class RandomAreaFarmPath(AbstractFarmPath):
    
    def __init__(
        self,
        name: str,
        startVertex: Vertex,
        allowedTransitions: list = None,
        subAreaBlacklist: list = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.startVertex = startVertex
        self.allowedTransitions: list[TransitionTypeEnum] = allowedTransitions
        self.subAreaBlacklist = subAreaBlacklist if subAreaBlacklist is not None else []

    def init(self):
        self.area = SubArea.getSubAreaByMapId(self.startVertex.mapId).area
        self.subAreas = self.getAllSubAreas()
        Logger().info(f"RandomAreaFarmPath {self.name} initialized with {len(self.vertices)} vertices")

    @property
    def mapIds(self) -> Set[int]:
        if not self._mapIds:
            self._mapIds = self.getAllMapsIds()
        return self._mapIds

    @property
    def pourcentExplored(self):
        return 100 * len(self._lastVisited) / len(self.vertices)

    def getClosestUnvisited(self):
        bestDist = float("inf")
        bestSolution = None
        currMp = MapPosition.getMapPositionById(self.currentVertex.mapId)
        for v in self.vertices:
            if v.mapId == self.currentVertex.mapId:
                continue
            if v not in self._lastVisited:
                vMp = MapPosition.getMapPositionById(v.mapId)
                dist = abs(currMp.posX - vMp.posX) + abs(currMp.posY - vMp.posY)
                if dist < bestDist:
                    bestDist = dist
                    bestSolution = v
        if bestSolution is None:
            Logger().error(f"No unvisited vertex found")
        return bestSolution
    
    def getNextEdge(self, forbiddenEdges=None, onlyNonRecent=False) -> Vertex:
        outgoingEdges = list(self.outgoingEdges(onlyNonRecentVisited=onlyNonRecent))
        if forbiddenEdges is not None:
            if not isinstance(forbiddenEdges, (list, set)):
                raise ValueError(f"ForbiddenEdges must be a list or a set")
            outgoingEdges = [e for e in outgoingEdges if e not in forbiddenEdges]
        if not outgoingEdges:
            raise NoTransitionFound()
        edge = random.choice(outgoingEdges)
        return edge
    
    def __next__(self) -> Edge:
        outgoingEdges = list(self.outgoingEdges())
        if not outgoingEdges:
            raise NoTransitionFound()
        edge = random.choice(outgoingEdges)
        return edge
    
    def hasValidTransition(self, edge: Edge) -> bool:
        from pydofus2.com.ankamagames.dofus.datacenter.items.criterion.GroupItemCriterion import \
            GroupItemCriterion

        if self.allowedTransitions:
            transitions = [tr for tr in edge.transitions if TransitionTypeEnum(tr.type) in self.allowedTransitions]
        else:
            transitions = edge.transitions
        
        valid = False
        for transition in transitions:
            
            if transition.criterion:
                if (
                    "&" not in transition.criterion
                    and "|" not in transition.criterion
                    and transition.criterion[0:2] not in AStar.CRITERION_WHITE_LIST
                ):
                    return False
                criterion = GroupItemCriterion(transition.criterion)
                return criterion.isRespected
            valid = True
        return valid
    
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
                            if perf_counter() - self._lastVisited[edge.dst] > 60 * 60:
                                ret.append(edge)
                        else:
                            ret.append(edge)
                    else:
                        ret.append(edge)
        return ret
    
    def __iter__(self) -> Iterator[Vertex]:
        for it in self.vertices:
            yield it

    def __in__(self, vertex: Vertex) -> bool:
        return vertex in self.vertices
    
    def getAllSubAreas(self):
        subAreas = []
        for sa in SubArea.getAllSubArea():
            if sa.areaId == self.area.id:
                subAreas.append(sa)
        return subAreas
    
    def getAllMapsIds(self) -> Set[int]:
        mapIds = set[int]()
        for sa in self.subAreas:
            for mapId in sa.mapIds:
                if SubArea.getSubAreaByMapId(mapId).id not in self.subAreaBlacklist:
                    mapIds.add(mapId)
        return mapIds

    def to_json(self) -> dict:
        return {
            "type": self.__class__.__name__,
            "name": self.name,
            "areaId": self.area.id,
            "startVertex": {
                "mapId": self.startVertex.mapId,
                "mapRpZone": self.startVertex.zoneId,
            },
            "allowedTransitions": self.allowedTransitions,
            "subAreaBlacklist": self.subAreaBlacklist,
        }
