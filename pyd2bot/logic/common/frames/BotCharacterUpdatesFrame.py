import pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler as connh
from pyd2bot.logic.managers.BotConfig import BotConfig
from pydofus2.com.ankamagames.dofus.datacenter.breeds.Breed import Breed
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.messages.game.achievement.AchievementFinishedMessage import (
    AchievementFinishedMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.achievement.AchievementRewardRequestMessage import (
    AchievementRewardRequestMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.character.stats.CharacterLevelUpMessage import (
    CharacterLevelUpMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.character.stats.CharacterStatsListMessage import (
    CharacterStatsListMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.stats.StatsUpgradeRequestMessage import (
    StatsUpgradeRequestMessage,
)
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority
from pydofus2.damageCalculation.tools.StatIds import StatIds


class BotCharacterUpdatesFrame(Frame):
    def __init__(self):
        self._statsInitialized = False
        super().__init__()

    def pushed(self) -> bool:
        return True

    def pulled(self) -> bool:
        return True

    @property
    def priority(self) -> int:
        return Priority.VERY_LOW

    def getStatFloor(self, statId: int):
        breed = Breed.getBreedById(PlayedCharacterManager().infos.breed)
        statFloors = {
            StatIds.STRENGTH: breed.statsPointsForStrength,
            StatIds.VITALITY: breed.statsPointsForVitality,
            StatIds.WISDOM: breed.statsPointsForWisdom,
            StatIds.INTELLIGENCE: breed.statsPointsForIntelligence,
            StatIds.AGILITY: breed.statsPointsForAgility,
            StatIds.CHANCE: breed.statsPointsForChance,
        }
        return statFloors[statId]

    def boostStat(self, statId: int, points: int):
        stat_floors = self.getStatFloor(statId)
        additional = PlayedCharacterManager().stats.getStatAdditionalValue(statId)
        base = PlayedCharacterManager().stats.getStatBaseValue(statId)
        current_stat_points = base + additional

        try:
            current_floor_cost = next(floor[1] for floor in stat_floors if floor[0] > current_stat_points)
        except StopIteration:
            # if there's no floor that the current stat points is less than
            current_floor_cost = 4

        boost = 0
        for i in range(len(stat_floors)):
            next_floor = stat_floors[i + 1][0] if i + 1 < len(stat_floors) else float("inf")
            pts_to_invest = min(points, next_floor - current_stat_points)
            additional_boost = pts_to_invest // current_floor_cost
            if additional_boost == 0:
                break
            boost += additional_boost
            points -= additional_boost * current_floor_cost
            current_floor_cost = stat_floors[i + 1][1] if i + 1 < len(stat_floors) else 4
        if boost > 0:
            sumsg = StatsUpgradeRequestMessage()
            sumsg.init(False, statId, boost)
            connh.ConnectionsHandler().send(sumsg)

    def process(self, msg: Message) -> bool:

        if isinstance(msg, AchievementFinishedMessage):
            msg.achievement.id
            arrmsg = AchievementRewardRequestMessage()
            arrmsg.init(msg.achievement.id)
            connh.ConnectionsHandler().send(arrmsg)
            return False

        elif isinstance(msg, CharacterLevelUpMessage):
            if BotConfig().primaryStatId:
                previousLevel = PlayedCharacterManager().infos.level
                PlayedCharacterManager().infos.level = msg.newLevel
                pointsEarned = (msg.newLevel - previousLevel) * 5
                self.boostStat(BotConfig().primaryStatId, pointsEarned)
            return True

        elif isinstance(msg, CharacterStatsListMessage):
            if not self._statsInitialized:
                unusedStatPoints = PlayedCharacterManager().stats.getStatBaseValue(StatIds.STATS_POINTS)
                if unusedStatPoints > 0:
                    self.boostStat(BotConfig().primaryStatId, unusedStatPoints)
                self._statsInitialized = True
            return True
