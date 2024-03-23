from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config
from typing import List, Optional
from enum import Enum
from marshmallow import fields

from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import WorldGraph
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.TransitionTypeEnum import TransitionTypeEnum
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex

class SessionStatus(Enum):
    CRASHED = 0
    TERMINATED = 1
    RUNNING = 2
    DISCONNECTED = 3
    AUTHENTICATING = 4
    FIGHTING = 5
    ROLEPLAYING = 6
    LOADING_MAP = 7
    PROCESSING_MAP = 8
    OUT_OF_ROLEPLAY = 9
    IDLE = 10
    BANNED = 11

@dataclass_json
@dataclass
class JobFilter:
    jobId: int
    resourcesIds: List[int]

@dataclass_json
@dataclass
class RunSummary:
    login: str
    startTime: int
    totalRunTime: int
    sessionId: str
    numberOfRestarts: int
    status: str
    earnedKamas: int
    nbrFightsDone: int
    earnedLevels: int
    leaderLogin: Optional[str] = None
    statusReason: Optional[str] = None

@dataclass_json
@dataclass
class CharacterDetails:
    level: int
    hp: int
    vertex: Vertex
    kamas: int
    areaName: str
    subAreaName: str
    cellId: int
    mapX: int
    mapY: int
    inventoryWeight: int
    shopWeight: int
    inventoryWeightMax: int

    @staticmethod
    def _vertex_factory(data):
        if data is not None:
            return Vertex.from_dict(data)
        return None
    
@dataclass_json
@dataclass
class Server:
    id: int
    name: str
    status: int
    completion: int
    charactersCount: int
    charactersSlots: int
    date: float
    isMonoAccount: bool
    isSelectable: bool

@dataclass_json
@dataclass
class Breed:
    id: int
    name: str

class SessionType(Enum):
    FIGHT = 0
    FARM = 1
    SELL = 3
    TREASURE_HUNT = 4
    MIXED = 5
    MULE_FIGHT = 6
    MULTIPLE_PATHS_FARM = 7


class UnloadType(Enum):
    BANK = 0
    STORAGE = 1
    SELLER = 2

class PathType(Enum):
    RandomSubAreaFarmPath = 0
    RandomAreaFarmPath = 2
    CyclicFarmPath = 1
    CustomRandomFarmPath = 3

@dataclass_json
@dataclass
class Path:
    id: str
    type: PathType
    startVertex: Optional[Vertex] = field(
        default=None, 
        metadata=config(
            encoder=lambda v: {'mapId': v.mapId, 'zoneId': v.zoneId} if v else None,
            decoder=lambda v: WorldGraph().getVertex(v['mapId'], v['zoneId']) if v else None,
            mm_field=fields.Function(
                serialize=lambda v: {'mapId': v.mapId, 'zoneId': v.zoneId} if v else None,
                deserialize=lambda v: WorldGraph().getVertex(v['mapId'], v['zoneId']) if v else None
            )
        )
    )
    transitionTypeWhitelist: Optional[List[TransitionTypeEnum]] = None
    subAreaBlacklist: Optional[List[int]] = None
    mapIds: Optional[List[int]] = None

@dataclass_json
@dataclass
class Spell:
    id: int
    name: str

@dataclass_json
@dataclass
class Character:
    name: str
    id: float
    level: int
    breedId: int
    breedName: str
    serverId: int
    serverName: str
    login: Optional[str] = None
    accountId: Optional[int] = None

@dataclass_json
@dataclass
class Certificate:
    id: int
    hash: str

@dataclass_json
@dataclass
class Session:
    id: str
    apikey: str
    character: Character
    type: SessionType
    unloadType: UnloadType
    leader: Optional[Character] = None
    followers: Optional[List[Character]] = None
    seller: Optional[Character] = None
    path: Optional[Path] = None
    monsterLvlCoefDiff: Optional[float] = None
    jobFilters: Optional[List[JobFilter]] = None
    cert: Optional[Certificate] = None
    pathsList: Optional[List[Path]] = None

@dataclass_json
@dataclass
class Account:
    id: int
    type: str
    login: str
    nickname: str
    firstname: str
    lastname: str
    nicknameWithTag: str
    tag: str
    security: List[str]
    addedDate: str
    locked: bool
    avatar: str
    apikey: Optional[str] = None
    certid: Optional[int] = 0
    certhash: Optional[str] = ""
    characters: Optional[List[Character]] = field(default_factory=list)
    parentEmailStatus: Optional[str] = None

    def get_character(self, charId=None) -> Character:
        if not self.characters:
            return None
        if charId is None:
            return self.characters[0]
        else:
            for ch in self.characters:
                if ch.id == float(charId):
                    return ch
        return None