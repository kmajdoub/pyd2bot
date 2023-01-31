from pyd2bot.thriftServer.pyd2botService.ttypes import Session, SessionType, Character, UnloadType
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.metaclasses.Singleton import Singleton
from pyd2bot.logic.managers.PathFactory import PathFactory
from enum import Enum


class CharacterRoleEnum(Enum):
    LEADER = 0
    FOLLOWER = 1
    SELLER = 2
class BotConfig(metaclass=Singleton):
    defaultBreedConfig = {
        10: { # sadida
            "primarySpellId" : 13516, # ronce
            "primaryStat" : 10 #  force
        },
        4 : { # sram
            "primarySpellId" : 12902, # Truanderie
            "primaryStat" : 10 # force
        },
    }
    def __init__(self) -> None:
        self.character: Character = None
        self.path = None
        self.isLeader: bool = None
        self.leader: Character = None
        self.followers: list[Character] = None
        self.jobIds: list[int] = None
        self.resourceIds: list[int] = None
        self.id = None
        self.sessionType: SessionType = None
        self.seller: Character = None
        self.unloadType: UnloadType = None
        self.monsterLvlCoefDiff = float('inf')
    
    @property
    def primarySpellId(self) -> int:
        return self.defaultBreedConfig[self.character.breedId]["primarySpellId"]
    
    @property
    def primaryStatId(self) -> int:
        return self.defaultBreedConfig[self.character.breedId]["primaryStat"]
    
    @property
    def unloadInBank(self) -> bool:
        return self.unloadType == UnloadType.BANK
    
    @property
    def unloadInSeller(self) -> bool:
        return self.unloadType == UnloadType.SELLER
    
    @property
    def isFarmSession(self) -> bool:
        return self.sessionType == SessionType.FARM
    
    @property
    def isFightSession(self) -> bool:
        return self.sessionType == SessionType.FIGHT
    
    def initFromSession(self, session: Session, role: CharacterRoleEnum, character: Character):
        self.id = session.id
        self.sessionType = session.type
        self.unloadType = session.unloadType
        self.followers = session.followers
        self.party = (self.followers is not None and len(self.followers) > 0)
        self.character = character
        self.isLeader = (role == CharacterRoleEnum.LEADER)
        if self.isFightSession and self.isLeader:
            self.path = PathFactory.from_thriftObj(session.path)
            self.monsterLvlCoefDiff = session.monsterLvlCoefDiff if session.monsterLvlCoefDiff is not None else float('inf')
        else:
            self.leader = session.leader
