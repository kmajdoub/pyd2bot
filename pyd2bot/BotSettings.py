import os
import threading

from pydofus2.com.ankamagames.dofus.network.enums.BreedEnum import BreedEnum
from pydofus2.damageCalculation.tools.StatIds import StatIds

BASEDIR = os.path.dirname(os.path.abspath(__file__))

class BotSettings:
    PERSISTENCE_DIR = os.path.join(os.getenv("APPDATA"), "pyd2bot", "persistence")
    KEYS_DIR = os.path.join(os.getenv("APPDATA"), "pyd2bot", "secrects", "vault")
    
    if not os.path.exists(PERSISTENCE_DIR):
        os.makedirs(PERSISTENCE_DIR)
    
    if not os.path.exists(KEYS_DIR):
        os.makedirs(KEYS_DIR)

    defaultBreedConfig = {
        BreedEnum.Sadida: {
            "primarySpellId": 13516, # ronce
            "primaryStat": StatIds.STRENGTH,
        },
        BreedEnum.Sram: {
            "primarySpellId": 12902, # Truanderie
            "primaryStat": StatIds.STRENGTH,
        },  
        BreedEnum.Cra: {
            "primarySpellId": 13047, # fleche optique
            "primaryStat": StatIds.AGILITY,
        },
        BreedEnum.Feca: {
            "primarySpellId": 12978, # attaque naturelle
            "primaryStat": StatIds.INTELLIGENCE,
        }
    }
    
    SELLER_VACANT = threading.Event()
    SELLER_LOCK = threading.Lock()
    TAKE_NAP_AFTTER_HOURS = 2
    NAP_DURATION_MINUTES = 20
