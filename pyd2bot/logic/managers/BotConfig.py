import threading
from typing import TYPE_CHECKING

from pyd2bot.logic.managers.PathFactory import PathFactory
from pyd2bot.models.session.models import Character, Path, Session, SessionType, UnloadType
from pydofus2.com.ankamagames.dofus.network.enums.BreedEnum import BreedEnum
from pydofus2.com.ankamagames.jerakine.metaclasses.Singleton import Singleton
from pydofus2.damageCalculation.tools.StatIds import StatIds

if TYPE_CHECKING:
    from pyd2bot.models.farmPaths.AbstractFarmPath import AbstractFarmPath


class BotConfig(metaclass=Singleton):
    SELLER_VACANT = threading.Event()
    SELLER_LOCK = threading.Lock()

    defaultBreedConfig = {
        BreedEnum.Sadida: {
            "primarySpellId": 13516, # ronce
            "primaryStat": StatIds.STRENGTH,
        },
        BreedEnum.Sram: {
            "primarySpellId": 12902, # Truanderie
            "primaryStat": StatIds.STRENGTH
        },  
        BreedEnum.Cra: {
            "primarySpellId": 13047, # fleche optique
            "primaryStat": StatIds.INTELLIGENCE
        }
    }

    def __init__(self) -> None:
        self.character: Character = None
        self.path: "AbstractFarmPath" = None
        self.isLeader: bool = None
        self.isSeller = None
        self.isFollower = None
        self.leader: Character = None
        self.followers: list[Character] = None
        self.jobIds: list[int] = None
        self.resourceIds: list[int] = None
        self.id = None
        self.sessionType: SessionType = None
        self.seller: Character = None
        self.unloadType: UnloadType = None
        self.monsterLvlCoefDiff = float("inf")
        self.fightOptionsSent = False
        self.lastFightTime = 0
        self.fightOptions = []
        self.followersIds = []
        self.fightPartyMembers = list[Character]()
        self.hasSellerLock = False
        self.pathsList: list[Path] = []

    def releaseSellerLock(self):
        if self.hasSellerLock:
            if BotConfig.SELLER_LOCK.locked():
                BotConfig.SELLER_LOCK.release()
            BotConfig.SELLER_VACANT.set()

    def getPrimarySpellId(self, breedId) -> int:
        return self.defaultBreedConfig[breedId]["primarySpellId"]

    def getSecondarySpellId(self, breedId) -> int:
        return self.defaultBreedConfig[breedId]["secondarySpellId"]

    @property
    def primaryStatId(self) -> int:
        return self.defaultBreedConfig[self.character.breedId]["primaryStat"]

    @property
    def unloadInBank(self) -> bool:
        return self.isSeller or self.unloadType == UnloadType.BANK

    @property
    def unloadInSeller(self) -> bool:
        return not self.isSeller and self.unloadType == UnloadType.SELLER

    @property
    def isFarmSession(self) -> bool:
        return self.sessionType == SessionType.FARM

    @property
    def isTreasureHuntSession(self) -> bool:
        return self.sessionType == SessionType.TREASURE_HUNT

    @property
    def isFightSession(self) -> bool:
        return self.sessionType == SessionType.FIGHT

    @property
    def isMixed(self) -> bool:
        return self.sessionType == SessionType.MIXED

    @property
    def isMultiPathsFarmer(self):
        return self.sessionType == SessionType.MULTIPLE_PATHS_FARM

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

    def initFromSession(self, session: Session):
        self.id = session.id
        if not session.jobFilters:
            session.jobFilters = []
        self.jobFilter = {jf.jobId: jf.resourcesIds for jf in session.jobFilters}
        self.sessionType = session.type
        self.unloadType = session.unloadType
        self.followers = session.followers if session.followers else []
        self.followersIds = [follower.id for follower in self.followers]
        self.party = self.followers is not None and len(self.followers) > 0
        self.character = session.character
        self.isLeader = session.type != SessionType.MULE_FIGHT
        self.isFollower = not self.isLeader
        self.isSeller = session.type == SessionType.SELL
        self.seller = session.seller
        if session.pathsList:
            self.pathsList = [PathFactory.from_dto(path) for path in session.pathsList]
        if session.path:
            self.path = PathFactory.from_dto(session.path)
        elif session.type in [SessionType.FARM, SessionType.FIGHT]:
            raise ValueError("Session path is required for farm and fight sessions")
        if self.monsterLvlCoefDiff:
            self.monsterLvlCoefDiff = (
                session.monsterLvlCoefDiff if session.monsterLvlCoefDiff is not None else float("inf")
            )
        self.leader = session.leader
        self.fightPartyMembers = self.followers + [self.character]
