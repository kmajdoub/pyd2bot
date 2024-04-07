import threading

from pyd2bot.data.models import PlayerStats
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.quest.ClassicTreasureHunt import ClassicTreasureHunt
from pydofus2.com.ankamagames.atouin.HaapiEventsManager import \
    HaapiEventsManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.messages.game.achievement.AchievementRewardRequestMessage import \
    AchievementRewardRequestMessage
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.job.JobExperience import JobExperience
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class CollectStats(AbstractBehavior):

    def __init__(self, listeners: list[callable]=None):
        super().__init__()
        self.playerStats = PlayerStats()
        self.totalKamas = None
        if listeners is None:
            listeners = []
        self.listeners = listeners

    def run(self) -> bool:
        self.onMultiple(
            [
                (KernelEvent.PlayerLeveledUp, self.onPlayerLevelUp, {}), 
                (KernelEvent.AchievementFinished, self.onAchievementFinished, {}),
                (KernelEvent.ObtainedItem, self.onItemObtained, {}),
                (KernelEvent.ObjectAdded, self.onObjectAdded, {}),
                (KernelEvent.MapDataProcessed, self.onMapDataProcessed, {}),
                (KernelEvent.JobLevelUp, self.onJobLevelUp, {}),
                (KernelEvent.JobExperienceUpdate, self.onJobExperience, {}),
                (KernelEvent.KamasUpdate, self.onKamasUpdate, {}),
                (KernelEvent.FightStarted, self.onFight, {}),
            ]
        )
        self.waitingForCharactsBoost = threading.Event()
        return True
    
    def addHandler(self, callback):
        self.listeners.append(callback)
    
    def removeHandler(self, callback):
        self.listeners.remove(callback)

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
        HaapiEventsManager().sendRandomEvent()
        if iw.objectGID not in ClassicTreasureHunt.CHESTS_GUID:
            averageKamasWon = (
                Kernel().averagePricesFrame.getItemAveragePrice(iw.objectGID) * qty
            )
            Logger().debug(f"Average kamas won from item : {averageKamasWon}")
            self.estimated_kamas_won += averageKamasWon
        self.playerStats.itemsGained.append((iw.objectGID, qty))
        self.onPlayerUpdate(event)

    def onObjectAdded(self, event, iw):
        HaapiEventsManager().sendRandomEvent()
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
        HaapiEventsManager().sendRandomEvent()
    
    def onAchievementFinished(self, event, achievement):
        if PlayedCharacterManager().isFighting:
            return
        arrmsg = AchievementRewardRequestMessage()
        arrmsg.init(achievement.id)
        ConnectionsHandler().send(arrmsg)
        HaapiEventsManager().sendRandomEvent()
        return True

    def onFight(self, event):
        self.playerStats.nbrFightsDone += 1
        self.onPlayerUpdate(event)
