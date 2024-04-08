from pydantic import BaseModel, ValidationError, ValidationInfo, field_validator, model_validator
from typing import Dict, List, Optional

from pydantic_core import PydanticCustomError
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

class JobFilter(BaseModel):
    jobId: int
    resourcesIds: List[int]

    @model_validator(mode="after")
    def validate(self):
        job = Job.getJobById(self.jobId)
        if not job:
            raise ValueError(f"JobId '{self.jobId}' does not match any valid job.")

        skills = Skill.getSkills()
        possiblegatheredRessources = [skill.gatheredRessource.id for skill in skills if skill.parentJobId == self.jobId]
        for resId in self.resourcesIds:
            assert (
                resId in possiblegatheredRessources
            ), f"ResourcesIds contains a value '{resId}' that does not match any possible gathered resource for the specified job."


class Path(BaseModel):
    id: str
    type: PathTypeEnum
    startMapId: Optional[float] = None
    startZoneId: Optional[int] = None
    allowedTransitions: Optional[List[TransitionTypeEnum]] = None
    forbiddenSubAreas: Optional[List[int]] = None
    mapIds: Optional[List[int]] = None

    @field_validator("startMapId", mode="before")
    @classmethod
    def check_start_map_id(cls, v: float, info: ValidationInfo):
        if info.data["type"] in [PathTypeEnum.RandomAreaFarmPath, PathTypeEnum.RandomSubAreaFarmPath]:
            if not v:
                raise ValueError("StartMapId is required for this type of path.")
            if not WorldGraph().getVertices(v):
                raise ValueError(f"Value did not match any valid vertex.")
        return v

    @field_validator("startZoneId", mode="after")
    @classmethod
    def check_start_zone_id(cls, v: int, info: ValidationInfo):
        if v is None or "startMapId" not in info.data:
            return v
        if info.data["type"] in [PathTypeEnum.RandomAreaFarmPath, PathTypeEnum.RandomSubAreaFarmPath]:
            if not WorldGraph().getVertex(info.data["startMapId"], v):
                raise ValueError(f"'{info.data['startMapId']}', has no roleplay zone with id {v}.")
        return v
    
    @field_validator("forbiddenSubAreas", mode="after")
    @classmethod
    def check_forbidden_sub_areas(cls, v: List[int], info: ValidationInfo):
        if v is None:
            return v
        if info.data["type"] in [PathTypeEnum.RandomAreaFarmPath, PathTypeEnum.RandomSubAreaFarmPath]:
            invalid_subAreas = [subAreaId for subAreaId in v if not SubArea.getSubAreaById(subAreaId)]
            if invalid_subAreas:
                raise ValueError(f"Following ids doesnt much an existing subArea: {invalid_subAreas}.")
        return v
    
    @field_validator("mapIds", mode="after")
    @classmethod
    def check_map_ids(cls, v: List[int], info: ValidationInfo):
        if info.data["type"] in [PathTypeEnum.CustomRandomFarmPath]:
            invalid_mapIds = [map_id for map_id in v if not WorldGraph().getVertices(map_id)]
            if invalid_mapIds:
                raise ValueError(f"Following ids doesnt much an existing map: {invalid_mapIds}.")
        return v

class Character(BaseModel):
    name: str
    id: float
    level: int
    breedId: int
    breedName: str
    serverId: int
    serverName: str
    accountId: int

    @field_validator("serverId", "breedId")
    @classmethod
    def check_server_and_breed(cls, v: int, info: ValidationInfo):
        if info.field_name == "serverId":
            assert Server.getServerById(v), f"'{v}' is not a valid server id."
        if info.field_name == "breedId":
            assert Breed.getBreedById(v), f"'{v}' is not a valid breed id."
        return v

    @field_validator("breedId")
    @classmethod
    def check_primary_spell_id(cls, breedId, info: ValidationInfo):
        if breedId not in BotSettings.defaultBreedConfig:
            raise ValueError(f"Primary spell not defined for breed {info.data.get('breedName', 'Unknown')}.")
        if "primarySpellId" not in BotSettings.defaultBreedConfig[breedId]:
            raise ValueError(f"Primary spell not defined for breed {info.data.get('breedName', 'Unknown')}.")
        return breedId

    @property
    def primarySpellId(self) -> int:
        return BotSettings.defaultBreedConfig[self.breedId]["primarySpellId"]

    @property
    def primaryStatId(self) -> int:
        return BotSettings.defaultBreedConfig[self.breedId]["primaryStat"]


class Credentials(BaseModel):
    apikey: str
    certId: Optional[int] = 0
    certHash: Optional[str] = ""


class Session(BaseModel):
    id: str
    character: Character
    type: SessionTypeEnum
    credentials: Credentials
    unloadType: UnloadTypeEnum = UnloadTypeEnum.BANK
    leader: Optional[Character] = None
    followers: List[Character] = []
    seller: Optional[Character] = None
    path: Optional[Path] = None
    monsterLvlCoefDiff: float = 10.0
    jobFilters: List[JobFilter] = []
    pathsList: Optional[List[Path]] = None
    fightsPerMinute: float = 1
    numberOfCovers: int = 3
    fightOptionsSent: bool = False

    @model_validator(mode="before")
    @classmethod
    def validate(cls, data):
        cls.check_logic(data)

    @classmethod
    def check_logic(cls, data):
        isSeller = data.get("type") == SessionTypeEnum.SELL.value
        isMuleFighter = data.get("type") == SessionTypeEnum.MULE_FIGHT.value
        unloadInBank = data.get("unloadType") == UnloadTypeEnum.BANK.value
        unloadInSeller = data.get("unloadType") == UnloadTypeEnum.SELLER.value
        isFarmSession = data.get("type") == SessionTypeEnum.FARM.value
        isFightSession = data.get("type") == SessionTypeEnum.FIGHT.value
        isMultiPathsFarmer = data.get("type") == SessionTypeEnum.MULTIPLE_PATHS_FARM.value
        seller = data.get("seller")
        leader = data.get("leader")
        path = data.get("path")
        pathsList = data.get("pathsList")
        if not seller:
            if isSeller:
                raise ValueError("Seller session must have a seller character.")
            if unloadInSeller:
                raise ValueError("Seller unload type must have a seller character.")
        else:
            if unloadInBank:
                raise ValueError("Bank unload type must not have a seller character.")
    
        if isMuleFighter and not leader:
            raise ValueError("Mule fighter session must have a leader character.")

        if isFarmSession and not path:
            raise ValueError("Farm session must have a path.")

        if isFightSession and not path:
            raise ValueError("Fight session must have a path.")

        if isMultiPathsFarmer and (pathsList is None or len(pathsList) < 2):
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


class Account(BaseModel):
    id: int
    type: str
    login: str
    nickname: str
    firstname: str
    lastname: str
    nicknameWithTag: str
    tag: int
    security: List[str]
    addedDate: str  # Consider using datetime for date handling
    locked: bool
    avatar: str
    apikey: Optional[str] = None
    certId: Optional[int] = 0
    certHash: Optional[str] = ""
    characters: List[Character] = []
    parentEmailStatus: Optional[str] = None

    def get_character(self, charId: Optional[int] = None) -> Optional[Character]:
        if charId is None:
            return self.characters[0] if self.characters else None
        for character in self.characters:
            if character.id == charId:
                return character
        return None

    @property
    def credentials(self) -> "Credentials":
        return Credentials(apikey=self.apikey, certId=self.certId, certHash=self.certHash)


class PlayerStats(BaseModel):
    earnedKamas: int = 0
    earnedLevels: int = 0
    nbrFightsDone: int = 0
    nbrTreasuresHuntsDone: int = 0
    estimatedKamasWon: int = 0
    nbrOfDeaths: int = 0
    kamasSpentTeleporting: int = 0
    numberOfTeleports: int = 0
    kamasSpentOpeningBank: int = 0
    currLevelEarnedXpPercentage: float = 0.0
    earnedJobLevels: Dict[int, int] = {}
    itemsGained: Dict[int, int] = {}
    visitedMapsHeatMap: Dict[int, int] = {}

    def add_job_level(self, job_id: str, levels_gained: int) -> None:
        self.earnedJobLevels[job_id] = self.earnedJobLevels.get(job_id, 0) + levels_gained

    def add_item_gained(self, item_guid, qty) -> None:
        self.itemsGained[item_guid] = self.itemsGained.get(item_guid, 0) + qty

    def add_visited_map(self, map_id: int) -> None:
        self.visitedMapsHeatMap[map_id] = self.visitedMapsHeatMap.get(map_id, 0) + 1
