from enum import Enum


class ServerNotificationEnum:
    FULL_PODS = 756273
    DOESNT_HAVE_LVL_FOR_HAVEN_BAG = 589049
    CANT_USE_HAVEN_BAG_FROM_CURRMAP = 589088
    MOUNT_HAS_NO_ENERGY_LEFT = 5336
    INACTIVITY_WARNING = 5123
    KAMAS_GAINED = 325840
    KAMAS_LOST = 325865

class SessionTypeEnum(str, Enum):
    SOLO_FIGHT = 'SOLO_FIGHT'
    GROUP_FIGHT = 'GROUP_FIGHT'
    FARM = 'FARM'
    SELL = 'SELL'
    TREASURE_HUNT = 'TREASURE_HUNT'
    MIXED = 'MIXED'
    MULE_FIGHT = 'MULE_FIGHT'
    MULTIPLE_PATHS_FARM = 'MULTIPLE_PATHS_FARM'

class UnloadTypeEnum(str, Enum):
    BANK = 'BANK'
    STORAGE = 'STORAGE'
    SELLER = 'SELLER'

class PathTypeEnum(str, Enum):
    RandomSubAreaFarmPath = 'RandomSubAreaFarmPath'
    RandomAreaFarmPath = 'RandomAreaFarmPath'
    CyclicFarmPath = 'CyclicFarmPath'
    CustomRandomFarmPath = 'CustomRandomFarmPath'