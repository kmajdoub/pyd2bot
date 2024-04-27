from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.TransitionTypeEnum import \
    TransitionTypeEnum
from typing import TYPE_CHECKING, Iterator, List
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.astar.AStar import \
    AStar
from pyd2bot.misc.Localizer import Localizer
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Transition import \
    Transition
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import \
    WorldGraph
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
import collections
from typing import Iterator, Set
if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import Edge
    from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex
class AbstractFarmPath:
    _currentVertex: 'Vertex'
    startVertex: 'Vertex'
    name : str
    _lastVisited : dict['Edge', int]
    _mapIds : list[int]
    _vertices: set['Vertex']

    def __init__(self) -> None:
        self._lastVisited = dict()
        self.name = "undefined"
        self._mapIds = []
        self._vertices = set()

    @property
    def vertices(self) -> Set['Vertex']:
        if not self._vertices:
            self._vertices = self.reachableVertices()
        return self._vertices
    
    @property
    def mapIds(self) -> list[int]:
        raise NotImplementedError()

    @property
    def currentVertex(self) -> 'Vertex':
        return PlayedCharacterManager().currVertex

    def outgoingEdges(self) -> Iterator['Edge']:
        raise NotImplementedError()
    
    def __next__(self) -> Transition:
        raise NotImplementedError()
    
    def getNextEdge(self, forbiddenEdges=None, onlyNonRecent=False) -> 'Edge':
        raise NotImplementedError()
    
    def __iter__(self) -> Iterator['Vertex']:
        for it in self.vertices:
            yield it

    def __in__(self, vertex: 'Vertex') -> bool:
        return vertex in self.vertices


    def currNeighbors(self) -> Iterator['Vertex']:
        raise NotImplementedError()

    def to_json(self):
        raise NotImplementedError()

    def init(self):
        raise NotImplementedError()
    
    @classmethod
    def from_json(cls, pathJson) -> "AbstractFarmPath":
        raise NotImplementedError()
    
    def findPathToClosestMap(self) -> List['Edge']:
        Logger().info(f"Looking for a path to the closest parkour map, starting from the current vertex...")
        candidates = []
        for dst_mapId in self.mapIds:
            vertices = WorldGraph().getVertices(dst_mapId)
            if vertices:
                candidates.extend(vertices.values())
        return Localizer.findPathToClosestVertexCandidate(self.currentVertex, candidates)

    def hasValidTransition(self, edge: 'Edge') -> bool:
        from pydofus2.com.ankamagames.dofus.datacenter.items.criterion.GroupItemCriterion import \
            GroupItemCriterion

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

    def reachableVertices(self) -> Set['Vertex']:
        queue = collections.deque([self.startVertex])
        vertices = set([self.startVertex])
        while queue:
            curr = queue.popleft()
            for e in self.outgoingEdges(curr):
                if e.dst not in vertices:
                    queue.append(e.dst)
                    vertices.add(e.dst)
        return vertices

    @staticmethod
    def filter_out_transitions(edge: 'Edge', tr_types_whitelist: list[TransitionTypeEnum]) -> bool:
        for tr in edge.transitions:
            if TransitionTypeEnum(tr.type) not in tr_types_whitelist:
                edge.transitions.remove(tr)
        return edge