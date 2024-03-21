from time import perf_counter
from typing import TYPE_CHECKING, Iterator

from pyd2bot.misc.Localizer import Localizer
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Transition import \
    Transition
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import \
    Vertex
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import \
    WorldGraph
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import \
        Edge

class AbstractFarmPath:
    fightOnly: bool
    _currentVertex: Vertex
    startVertex: Vertex
    skills = []
    jobIds = []
    monsterLvlCoefDiff = float("inf")
    name : str
    lastVisited : dict['Edge', int]
    _mapIds : list[int]

    def __init__(self) -> None:
        self.lastVisited = dict()
        self.name = "undefined"
        self._mapIds = []

    @property
    def mapIds(self) -> list[int]:
        raise NotImplementedError()

    @property
    def currentVertex(self) -> Vertex:
        return PlayedCharacterManager().currVertex

    def outgoingEdges(self) -> Iterator['Edge']:
        raise NotImplementedError()
    
    def __next__(self) -> Transition:
        raise NotImplementedError()
    
    def getNextVertex(self, forbidenEdges=None, onlyNonRecent=False) -> Vertex:
        raise NotImplementedError()
    
    def __in__(self, v: Vertex) -> bool:
        raise NotImplementedError()

    def __iter__(self) -> Iterator[Vertex]:
        raise NotImplementedError()

    def currNeighbors(self) -> Iterator[Vertex]:
        raise NotImplementedError()

    def to_json(self):
        raise NotImplementedError()

    def init(self):
        raise NotImplementedError()

    def findClosestMap(self) -> Vertex:
        raise NotImplementedError()
    
    @classmethod
    def from_json(cls, pathJson) -> "AbstractFarmPath":
        raise NotImplementedError()
    
    def findClosestMap(self):
        Logger().info(f"Searching closest path map from vertex")
        candidates = []
        for dst_mapId in self.mapIds:
            verticies = WorldGraph().getVertices(dst_mapId)
            if verticies:
                candidates.extend(verticies.values())
        v = Localizer.findClosestVertexFromVerticies(self.currentVertex, candidates)
        return v