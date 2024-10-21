import random
import time
from typing import Iterator, Set

from pyd2bot.farmPaths.AbstractFarmPath import AbstractFarmPath
from pyd2bot.farmPaths.RandomAreaFarmPath import NoTransitionFound
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


class RandomSubAreaFarmPath(AbstractFarmPath):
    def __init__(
        self,
        name: str,
        startVertex: Vertex,
        allowedTransitions: list = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.startVertex = startVertex
        self.allowedTransitions = allowedTransitions
        self._subArea = None
    
    @property
    def mapIds(self) -> Set[int]:
        if not self._subArea:
            self._subArea = SubArea.getSubAreaByMapId(self.startVertex.mapId)
        return self._subArea.mapIds

    def init(self):
        self._subArea = SubArea.getSubAreaByMapId(self.startVertex.mapId)
        Logger().info(f"RandomSubAreaFarmPath {self.name} initialized with {len(self.vertices)} vertices")

    def recentVisitedVertices(self):
        self._recent_visited = [(_, time_added) for (_, time_added) in self._recent_visited if (time.time() - time_added) < 60 * 5]
        return [v for v, _ in self._recent_visited]
    
    def __next__(self, forbiddenEdges) -> Edge:
        outgoingEdges = list(self.outgoingEdges(onlyNonRecentVisited=True))
        outgoingEdges = [e for e in outgoingEdges if e not in forbiddenEdges]
        if not outgoingEdges:
            raise NoTransitionFound()
        edge = random.choice(outgoingEdges)
        return edge

    def currNeighbors(self) -> Iterator[Vertex]:
        return self.outgoingEdges(self.currentVertex)

    def filter_out_transitions(self, edge: Edge, whitelist: list[TransitionTypeEnum]) -> bool:
        for tr in edge.transitions:
            if TransitionTypeEnum(tr.type) not in whitelist:
                edge.transitions.remove(tr)
        return edge
    
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

    def __iter__(self) -> Iterator[Vertex]:
        for it in self.vertices:
            yield it

    def __in__(self, vertex: Vertex) -> bool:
        return vertex in self.vertices

    def to_json(self) -> dict:
        return {
            "type": self.__class__.__name__,
            "name": self.name,
            "subAreaId": self._subArea.id,
            "startVertex": {
                "mapId": self.startVertex.mapId,
                "mapRpZone": self.startVertex.zoneId,
            },
            "allowedTransitions": self.allowedTransitions,
        }

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
    
    def getNextEdge(self, forbiddenEdges=None, onlyNonRecent=False) -> Vertex:
        outgoingEdges = list(self.outgoingEdges(onlyNonRecentVisited=onlyNonRecent))
        if forbiddenEdges is None:
            forbiddenEdges = []
        outgoingEdges = [e for e in outgoingEdges if e not in forbiddenEdges]
        if not outgoingEdges:
            raise NoTransitionFound()
        edge = random.choice(outgoingEdges)
        return edge
    