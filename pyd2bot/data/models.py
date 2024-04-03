from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config
from typing import List, Optional
from marshmallow import fields

from pyd2bot.BotSettings import BotSettings
from pyd2bot.logic.managers.PathFactory import PathFactory
from pyd2bot.data.enums import PathTypeEnum, SessionTypeEnum, UnloadTypeEnum
from pyd2bot.farmPaths.AbstractFarmPath import AbstractFarmPath
from pydofus2.com.ankamagames.dofus.datacenter.breeds.Breed import Breed
from pydofus2.com.ankamagames.dofus.datacenter.jobs.Job import Job
from pydofus2.com.ankamagames.dofus.datacenter.jobs.Skill import Skill
from pydofus2.com.ankamagames.dofus.datacenter.servers.Server import Server
from pydofus2.com.ankamagames.dofus.datacenter.world.SubArea import SubArea
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import WorldGraph
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.TransitionTypeEnum import TransitionTypeEnum
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex


@dataclass_json
@dataclass
class JobFilter:
    jobId: int
    resourcesIds: List[int]

    def __post_init__(self):
        self.validate()

    def validate(self):
        job = Job.getJobById(self.jobId)
        if not job:
            raise ValueError(f"Invalid job id {self.jobId}. Must be a valid job id.")
        skills = Skill.getSkills()
        possiblegatheredRessources = [
            skill.gatheredRessource.id for skill in skills if skill.parentJobId == self.jobId
        ]
        for resId in self.resourcesIds:
            if resId not in possiblegatheredRessources:
                raise ValueError(f"Invalid resource id {resId}. Must be a valid resource id for job {job.name}.")


@dataclass_json
@dataclass
class Path:
    id: str
    type: PathTypeEnum
    startVertex: Optional[Vertex] = field(
        default=None,
        metadata=config(
            encoder=lambda v: {"mapId": v.mapId, "zoneId": v.zoneId} if v else None,
            decoder=lambda v: WorldGraph().getVertex(v["mapId"], v["zoneId"]) if v else None,
            mm_field=fields.Function(
                serialize=lambda v: {"mapId": v.mapId, "zoneId": v.zoneId} if v else None,
                deserialize=lambda v: WorldGraph().getVertex(v["mapId"], v["zoneId"]) if v else None,
            ),
        ),
    )
    allowedTransitions: Optional[List[TransitionTypeEnum]] = None
    forbidenSubAreas: Optional[List[int]] = None
    mapIds: Optional[List[int]] = None

    def __post_init__(self):
        self.validate()

    def validate(self):
        if self.mapIds:
            for mapId in self.mapIds:
                if not WorldGraph().getVertices(mapId):
                    raise ValueError(f"Invalid value: {mapId}. Must be a valid map id.")
        if self.forbidenSubAreas:
            for subAreaId in self.forbidenSubAreas:
                if not SubArea.getSubAreaById(subAreaId):
                    raise ValueError(f"Invalid value: {subAreaId}. Must be a valid sub area id.")


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
    login: str
    accountId: Optional[int] = None

    def __post_init__(self):
        self.validate()

    def validate(self):
        if not Server.getServerById(self.serverId):
            raise ValueError(f"Invalid value: {self.serverId}. Must be a valid server id.")
        if not Breed.getBreedById(self.breedId):
            raise ValueError(f"Invalid value: {self.breedId}. Must be a valid breed id.")
        self.primarySpellId
        self.primaryStatId

    @property
    def primarySpellId(self) -> int:
        if self.breedId not in BotSettings.defaultBreedConfig:
            raise ValueError(
                f"Primary spell not defined for breed {self.breedName}. You need to add it the BotSettings module 'defaultBreedConfig' dict."
            )
        if "primarySpellId" not in BotSettings.defaultBreedConfig[self.breedId]:
            raise ValueError(
                f"Primary spell not defined for breed {self.breedName}. You need to add it the BotSettings module 'defaultBreedConfig' dict."
            )
        return BotSettings.defaultBreedConfig[self.breedId]["primarySpellId"]

    @property
    def primaryStatId(self) -> int:
        if self.breedId not in BotSettings.defaultBreedConfig:
            raise ValueError(
                f"Primary stat not defined for breed {self.breedName}. You need to add it the BotSettings module 'defaultBreedConfig' dict."
            )
        if "primaryStat" not in BotSettings.defaultBreedConfig[self.breedId]:
            raise ValueError(
                f"Primary stat not defined for breed {self.breedName}. You need to add it the BotSettings module 'defaultBreedConfig' dict."
            )
        return BotSettings.defaultBreedConfig[self.breedId]["primaryStat"]


@dataclass_json
@dataclass
class Credentials:
    apikey: str
    certId: Optional[int] = 0
    certHash: Optional[str] = ""


@dataclass_json
@dataclass
class Session:
    id: str
    character: Character
    type: SessionTypeEnum
    credentials: Credentials
    unloadType: Optional[UnloadTypeEnum] = UnloadTypeEnum.BANK
    leader: Optional[Character] = None
    followers: Optional[List[Character]] = field(default_factory=list)
    seller: Optional[Character] = None
    path: Optional[Path] = None
    monsterLvlCoefDiff: Optional[float] = 10.0
    jobFilters: Optional[List[JobFilter]] = field(default_factory=list)
    pathsList: Optional[List[Path]] = None
    fightsPerMinute: Optional[float] = 1
    number_of_covers: Optional[int] = 3
    fightOptionsSent: Optional[bool] = False

    def __post_init__(self):
        self.validate()

    def validate(self):
        if self.isSeller and not self.seller:
            raise ValueError("Seller session must have a seller character.")
        if self.isMuleFighter and not self.leader:
            raise ValueError("Mule fighter session must have a leader character.")
        if self.unloadInSeller and not self.seller:
            raise ValueError("Seller unload type must have a seller character.")
        if self.unloadInBank and self.seller:
            raise ValueError("Bank unload type must not have a seller character.")
        if self.isFarmSession and not self.path:
            raise ValueError("Farm session must have a path.")
        if self.isFightSession and not self.path:
            raise ValueError("Fight session must have a path.")
        if self.isMultiPathsFarmer and not self.pathsList:
            raise ValueError("Multi paths farm session must have a list of paths.")
        if self.isMultiPathsFarmer and len(self.pathsList) < 2:
            raise ValueError("Multi paths farm session must have at least 2 paths.")

    @property
    def fightPartyMembers(self):
        return self.followers + [self.character]

    @property
    def followersIds(self):
        return [f.id for f in self.followers]

    def getPlayerById(self, playerId: int) -> Character:
        if playerId == self.character.id:
            return self.character
        return self.getFollowerById(playerId)

    def getFollowerById(self, playerId) -> Character:
        for follower in self.followers:
            if follower.id == playerId:
                return follower

    def getFollowerByName(self, name) -> Character:
        for follower in self.followers:
            if follower.name == name:
                return follower

    @property
    def isSeller(self) -> bool:
        return self.type == SessionTypeEnum.SELL

    @property
    def unloadInBank(self) -> bool:
        return self.isSeller or self.unloadType == UnloadTypeEnum.BANK

    @property
    def unloadInSeller(self) -> bool:
        return not self.isSeller and self.unloadType == UnloadTypeEnum.SELLER

    @property
    def isFarmSession(self) -> bool:
        return self.type == SessionTypeEnum.FARM

    @property
    def isTreasureHuntSession(self) -> bool:
        return self.type == SessionTypeEnum.TREASURE_HUNT

    @property
    def isFightSession(self) -> bool:
        return self.type == SessionTypeEnum.FIGHT

    @property
    def isMixed(self) -> bool:
        return self.type == SessionTypeEnum.MIXED

    @property
    def isMultiPathsFarmer(self):
        return self.type == SessionTypeEnum.MULTIPLE_PATHS_FARM

    @property
    def isMuleFighter(self):
        return self.type == SessionTypeEnum.MULE_FIGHT

    def getPathFromDto(self) -> AbstractFarmPath:
        return PathFactory.from_dto(self.path)

    def getPathsListFromDto(self) -> List[AbstractFarmPath]:
        return [PathFactory.from_dto(path) for path in self.pathsList]


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

@dataclass_json
@dataclass
class PlayerStats:
    earnedKamas: int = 0
    earnedLevels: int = 0
    earnedJobLevels: dict = field(default_factory=dict)
    nbrFightsDone: int = 0
    estimatedKamasWon = 0
    itemsGained: List[str] = field(default_factory=list)