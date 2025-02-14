import os
import random
import threading
from typing import TYPE_CHECKING
from pydofus2.com.ankamagames.dofus.network.enums.BreedEnum import BreedEnum
from pydofus2.damageCalculation.tools.StatIds import StatIds

BASEDIR = os.path.dirname(os.path.abspath(__file__))
if TYPE_CHECKING:
    from pyd2bot.data.models import Session

class BotSettings:
    PERSISTENCE_DIR = os.path.join(os.getenv("APPDATA"), "pyd2bot", "persistence")
    KEYS_DIR = os.path.join(os.getenv("APPDATA"), "pyd2bot", "secrets", "vault")
    
    if not os.path.exists(PERSISTENCE_DIR):
        os.makedirs(PERSISTENCE_DIR)
    
    if not os.path.exists(KEYS_DIR):
        os.makedirs(KEYS_DIR)

    defaultBreedConfig = {
        BreedEnum.Sadida: {
            "primarySpellId": 13516, # Ronce
            "secondarySpellId": 13527,
            "treasureHuntFightSpellId": 13577,
            "primaryStat": StatIds.STRENGTH,
        },
        BreedEnum.Sram: {
            "primarySpellId": 12902, # Truanderie
            "treasureHuntFightSpellId": 12902,
            "primaryStat": StatIds.STRENGTH,
        },  
        BreedEnum.Cra: {
            "primarySpellId": 13047, # Fleche optique
            "treasureHuntFightSpellId": 13047,
            "primaryStat": StatIds.AGILITY,
        },
        BreedEnum.Feca: {
            "primarySpellId": 12978, # Attaque naturelle
            "treasureHuntFightSpellId": 12978,
            "primaryStat": StatIds.INTELLIGENCE,
        }
    }
    
    SELLER_VACANT = threading.Event()
    SELLER_LOCK = threading.Lock()

    # Static constants for random range
    MIN_NAP_AFTER_HOURS = 2.0
    MAX_NAP_AFTER_HOURS = 4.0
    MIN_NAP_DURATION_MINUTES = 10.0
    MAX_NAP_DURATION_MINUTES = 50.0
    REST_TIME_BETWEEN_HUNTS = 20

    @classmethod
    def generate_random_nap_timeout(cls):
        """Generate random nap timeout in hours in a predefined range"""
        return random.uniform(cls.MIN_NAP_AFTER_HOURS, cls.MAX_NAP_AFTER_HOURS)

    @classmethod
    def generate_random_nap_duration(cls):
        return random.uniform(cls.MIN_NAP_DURATION_MINUTES, cls.MAX_NAP_DURATION_MINUTES)
    
    @classmethod
    def checkBreed(self, session: "Session"):
        if session.character.breedId not in BotSettings.defaultBreedConfig:
            supported_breeds = [BreedEnum.get_name(breedId) for breedId in BotSettings.defaultBreedConfig]
            raise ValueError(
                f"Breed {session.character.breedName} is not supported, supported breeds are {supported_breeds}"
            )
