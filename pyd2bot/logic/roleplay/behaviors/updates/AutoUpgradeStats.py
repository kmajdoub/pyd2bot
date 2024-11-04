import threading

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.atouin.HaapiEventsManager import \
    HaapiEventsManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.datacenter.breeds.Breed import Breed
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.stats.StatsUpgradeRequestMessage import \
    StatsUpgradeRequestMessage
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.damageCalculation.tools.StatIds import StatIds


class AutoUpgradeStats(AbstractBehavior):

    def __init__(self, primaryStatId: int):
        super().__init__()
        self.primaryStatId = primaryStatId
        self.waitingForStatsBoost = threading.Event()
        self.IS_BACKGROUND_TASK = True

    def run(self) -> bool:
        self.on(KernelEvent.CharacterStats, self.onBotStats)

    def onBotStats(self, event, stats):
        if not Kernel().roleplayEntitiesFrame or not Kernel().roleplayEntitiesFrame.mcidm_processed:
            self.once_map_processed(lambda: self.onBotStats(event, stats))
            return
        unusedStatPoints = PlayedCharacterManager().stats.getStatBaseValue(StatIds.STATS_POINTS)
        if unusedStatPoints > 0 and not self.waitingForStatsBoost.is_set():
            boost, usedCapital = self.getBoost(unusedStatPoints)
            if boost > 0:
                Logger().info(f"Player can boost stat point with amount {boost}")
                HaapiEventsManager().sendCharacteristicsOpenEvent()
                self.waitingForStatsBoost.set()
                self.boostCharacteristics(usedCapital, self.primaryStatId)

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

    def getCurrCost(self, x, statFloors):
        currCost = None
        currFloorIdx = None
        for idx, interval in enumerate(statFloors):
            start, cost = interval
            if start <= x:
                currCost = cost
                currFloorIdx = idx
            else:
                break
        return currFloorIdx, currCost

    def getBoost(self, capital):
        statId = self.primaryStatId
        statFloors = self.getStatFloor(statId)
        additional = PlayedCharacterManager().stats.getStatAdditionalValue(statId)
        base = PlayedCharacterManager().stats.getStatBaseValue(statId)
        currentBase = base + additional
        idxCurrFloor, currentCost = self.getCurrCost(currentBase, statFloors)
        boost = 0
        usedCapital = 0
        while True:
            nextFloor = statFloors[idxCurrFloor + 1][0] if idxCurrFloor + 1 < len(statFloors) else float("inf")
            capitalUntilNextFloor = (nextFloor - currentBase) * currentCost
            if capital <= capitalUntilNextFloor:
                boost += capital // currentCost
                usedCapital += currentCost * (capital // currentCost)
                break
            else:
                usedCapital += capitalUntilNextFloor
                boost += nextFloor - currentBase
                currentBase = nextFloor
                capital -= capitalUntilNextFloor
                idxCurrFloor += 1
                currentCost = (
                    statFloors[idxCurrFloor][1]
                    if idxCurrFloor < len(statFloors)
                    else statFloors[len(statFloors) - 1][0]
                )
        return boost, usedCapital

    def boostCharacteristics(self, boost, statId):
        if PlayedCharacterManager().isFighting:
            return
        roleplay_frame = Kernel().roleplayEntitiesFrame
        if not roleplay_frame or not roleplay_frame.mcidm_processed:
            Logger().warning("Can't boost stats before map is fully loaded!")
            return self.once_map_processed(self.boostCharacteristics, [boost, statId])
        message = StatsUpgradeRequestMessage()
        message.init(False, statId, boost)
        ConnectionsHandler().send(message)
        self.once(KernelEvent.StatsUpgradeResult, self.onStatUpgradeResult)

    def onStatUpgradeResult(self, event, result, boost):
        self.waitingForStatsBoost.clear()
