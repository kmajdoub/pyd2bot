from enum import Enum


class TurnResult(Enum):
    SUCCESS = 0
    DISCONNECTED = 1
    NO_TARGETS = 2
    CANNOT_CAST = 3
    NO_PATH = 4
    PLAYER_DEAD = 5
    NO_FIGHTER_INFO = 6
    CANT_FIND_WAY_TO_HIT = 7
    INVALID_STATE = 8