import random
import threading

from pyd2bot.data.models import PlayerStats
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.quest.ClassicTreasureHunt import ClassicTreasureHunt
from pydofus2.com.ankamagames.atouin.HaapiEventsManager import \
    HaapiEventsManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.datacenter.breeds.Breed import Breed
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.messages.game.achievement.AchievementRewardRequestMessage import \
    AchievementRewardRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.stats.StatsUpgradeRequestMessage import \
    StatsUpgradeRequestMessage
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.job.JobExperience import JobExperience
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.damageCalculation.tools.StatIds import StatIds


class BotCharacterUpdates(AbstractBehavior):

    def __init__(self, primaryStatId: int, listeners: list[callable]=None):
        super().__init__()
        self.primaryStatId = primaryStatId
        self.playerStats = PlayerStats()
        self.totalKamas = None
        self.listeners = listeners

    def run(self) -> bool:
        self.onMultiple(
            [
                (KernelEvent.PlayerLeveledUp, self.onPlayerLevelUp, {}), 
                (KernelEvent.CharacterStats, self.onBotStats, {}),
                (KernelEvent.AchievementFinished, self.onAchievementFinished, {}),
                (KernelEvent.ObtainedItem, self.onItemObtained, {}),
                (KernelEvent.ObjectAdded, self.onObjectAdded, {}),
                (KernelEvent.MapDataProcessed, self.onMapDataProcessed, {}),
                (KernelEvent.JobLevelUp, self.onJobLevelUp, {}),
                (KernelEvent.JobExperienceUpdate, self.onJobExperience, {}),
                (KernelEvent.KamasUpdate, self.onKamasUpdate, {}),
                (KernelEvent.Restart, self.onRestart, {}),
                (KernelEvent.FightStarted, self.onFight, {}),
            ]
        )
        self.waitingForCharactsBoost = threading.Event()
        return True
    
    def onPlayerUpdate(self, event):
        if self.listeners:
            for listener in self.listeners:
                listener(event, self.playerStats)
    
    def onKamasUpdate(self, event, totalKamas):
        Logger().debug(f"Player kamas updated : {totalKamas}")
        if self.totalKamas is not None:
            diff = totalKamas - self.totalKamas
            if diff > 0:
                self.playerStats.earnedKamas += diff
        self.totalKamas = totalKamas
        self.onPlayerUpdate(event)
                      
    def onJobLevelUp(self, event, jobId, jobName, lastJobLevel, newLevel, podsBonus):
        HaapiEventsManager().sendProfessionsOpenEvent()
        Kernel().worker.terminated.wait(2)
        if jobId not in self.playerStats.earnedJobLevels:
            self.playerStats.earnedJobLevels[jobId] = 0
        self.playerStats.earnedJobLevels[jobId] += newLevel - lastJobLevel
        self.onPlayerUpdate(event)

    def onPlayerLevelUp(self, event, previousLevel, newLevel):
        HaapiEventsManager().sendInventoryOpenEvent()
        Kernel().worker.terminated.wait(2)
        HaapiEventsManager().sendSocialOpenEvent()
        Kernel().worker.terminated.wait(2)
        self.playerStats.earnedLevels += newLevel - previousLevel
        self.onPlayerUpdate(event)
                                        
    def onItemObtained(self, event, iw, qty):
        self.sendRandomEvent()
        if iw.objectGID not in ClassicTreasureHunt.CHESTS_GUID:
            averageKamasWon = (
                Kernel().averagePricesFrame.getItemAveragePrice(iw.objectGID) * qty
            )
            Logger().debug(f"Average kamas won from item : {averageKamasWon}")
            self.estimated_kamas_won += averageKamasWon
        self.playerStats.itemsGained.append((iw.objectGID, qty))
        self.onPlayerUpdate(event)

    def onObjectAdded(self, event, iw):
        self.sendRandomEvent()
        if iw.objectGID not in ClassicTreasureHunt.CHESTS_GUID:
            averageKamasWon = (
                Kernel().averagePricesFrame.getItemAveragePrice(iw.objectGID) * iw.quantity
            )
            Logger().debug(f"Average kamas won from item: {averageKamasWon}")
            self.estimated_kamas_won += averageKamasWon
        self.playerStats.itemsGained.append((iw.objectGID, iw.quantity))
        self.onPlayerUpdate(event)

    def onJobExperience(self, event, oldJobXp, jobExp: JobExperience):
        Logger().info(f"Job {jobExp.jobId} has gained {jobExp.jobXP} xp")

    def onMapDataProcessed(self, event, map):
        self.sendRandomEvent()
    
    def onAchievementFinished(self, event, achievement):
        if PlayedCharacterManager().isFighting:
            return
        arrmsg = AchievementRewardRequestMessage()
        arrmsg.init(achievement.id)
        ConnectionsHandler().send(arrmsg)
        return True

    def onFight(self, event):
        self.playerStats.nbrFightsDone += 1

    def sendRandomEvent(self):
        if random.random() < 0.1:
            HaapiEventsManager().sendMapOpenEvent()
            Kernel().worker.terminated.wait(2)
        elif random.random() < 0.1:
            if random.random() < 0.5:
                HaapiEventsManager().registerShortcutUse('openInventory')
                Kernel().worker.terminated.wait(0.2)
            else:
                HaapiEventsManager().sendInventoryOpenEvent()
                Kernel().worker.terminated.wait(2)
        elif random.random() < 0.1:
            HaapiEventsManager().sendSocialOpenEvent()
            Kernel().worker.terminated.wait(2)
        elif random.random() < 0.1:
            HaapiEventsManager().sendQuestsOpenEvent()
            Kernel().worker.terminated.wait(2)
        elif random.random() < 0.1:
            HaapiEventsManager().registerShortcutUse('openCharacterSheet')
            Kernel().worker.terminated.wait(2)

    def onBotStats(self, event=None):
        if not Kernel().roleplayEntitiesFrame or not Kernel().roleplayEntitiesFrame.mcidm_processed:
            Logger().info("waiting for map data to be processed before boosting stats ...")
            return KernelEventsManager().onceMapProcessed(self.onBotStats, originator=self)
        unusedStatPoints = PlayedCharacterManager().stats.getStatBaseValue(StatIds.STATS_POINTS)
        if unusedStatPoints > 0 and not self.waitingForCharactsBoost.is_set():
            boost, usedCapital = self.getBoost(unusedStatPoints)
            if boost > 0:
                Logger().info(f"Player can boost stat point with amount {boost}")
                HaapiEventsManager().sendCharacteristicsOpenEvent()
                self.waitingForCharactsBoost.set()
                self.boostCharacs(usedCapital, self.primaryStatId)

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

    def boostCharacs(self, boost, statId):
        rpeframe = Kernel().roleplayEntitiesFrame
        if not rpeframe or not rpeframe.mcidm_processed:
            return KernelEventsManager().onceMapProcessed(self.boostCharacs, [boost, statId], originator=self)
        sumsg = StatsUpgradeRequestMessage()
        sumsg.init(False, statId, boost)
        if PlayedCharacterManager().isFighting:
                return
        ConnectionsHandler().send(sumsg)
        KernelEventsManager().once(KernelEvent.StatsUpgradeResult, self.onStatUpgradeResult, originator=self)

    def onStatUpgradeResult(self, event, result, boost):
        self.waitingForCharactsBoost.clear()
