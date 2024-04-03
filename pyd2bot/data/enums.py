from enum import Enum


class ServerNotificationEnum:
    FULL_PODS = 756273
    DOESNT_HAVE_LVL_FOR_HAVEN_BAG = 589049
    CANT_USE_HAVEN_BAG_FROM_CURRMAP = 589088
    MOUNT_HAS_NO_ENERGY_LEFT = 5336
    INACTIVITY_WARNING = 5123
    KAMAS_GAINED = 325840

class SessionStatusEnum(Enum):
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

    @classmethod
    def choices(cls):
        return tuple((i.value, i.name) for i in cls)

class SessionTypeEnum(Enum):
    FIGHT = 0
    FARM = 1
    SELL = 3
    TREASURE_HUNT = 4
    MIXED = 5
    MULE_FIGHT = 6
    MULTIPLE_PATHS_FARM = 7

    @classmethod
    def choices(cls):
        return tuple((i.value, i.name) for i in cls)

class UnloadTypeEnum(Enum):
    BANK = 0
    STORAGE = 1
    SELLER = 2

    @classmethod
    def choices(cls):
        return tuple((i.value, i.name) for i in cls)

class PathTypeEnum(Enum):
    RandomSubAreaFarmPath = 0
    RandomAreaFarmPath = 2
    CyclicFarmPath = 1
    CustomRandomFarmPath = 3
    
    @classmethod
    def choices(cls):
        return tuple((i.value, i.name) for i in cls)

