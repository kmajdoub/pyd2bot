from typing import Iterator

from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Transition import \
    Transition
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import \
    Vertex


class AbstractFarmPath:
    fightOnly: bool
    _currentVertex: Vertex
    startVertex: Vertex
    skills = []
    jobIds = []
    monsterLvlCoefDiff = float("inf")
    name = "undefined"

    def __init__(self) -> None:
        pass

    @property
    def currentVertex(self) -> Transition:
        return PlayedCharacterManager().currVertex

    def __next__(self) -> Transition:
        raise NotImplementedError()

    def __in__(self, v: Vertex) -> bool:
        raise NotImplementedError()

    def __iter__(self) -> Iterator[Vertex]:
        raise NotImplementedError()

    def currNeighbors(self) -> Iterator[Vertex]:
        raise NotImplementedError()

    def neighbors(self, vertex: Vertex) -> Iterator[Vertex]:
        raise NotImplementedError()

    def to_json(self):
        raise NotImplementedError()

    @classmethod
    def from_json(cls, pathJson) -> "AbstractFarmPath":
        raise NotImplementedError()
