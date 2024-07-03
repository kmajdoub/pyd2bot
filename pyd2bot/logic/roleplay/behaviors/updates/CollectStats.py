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
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class CollectStats(AbstractBehavior):

    def __init__(self, listeners: list[callable]=None):
        super().__init__()
        self._oldStats = None
        self.playerStats = PlayerStats()
        self.initial_kamas = None
        if listeners is None:
            listeners = []
        self.update_listeners = listeners

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
                (KernelEvent.KamasLostFromTeleport, self.onKamasTeleport, {}),
                (KernelEvent.KamasGained, self.onKamasGained, {}),
                (KernelEvent.TreasureHuntFinished, self.onHuntFinished, {}),
                (KernelEvent.ZAAP_TELEPORT, self.onTeleportWithZaap, {}),
                (KernelEvent.KamasLostFromBankOpen, self.onLostKamasByBankOpen, {})
            ]
        )
        return True
    
    def addHandler(self, callback):
        self.update_listeners.append(callback)
    
    def removeHandler(self, callback):
        self.update_listeners.remove(callback)

    def onHuntFinished(self, event, questType):
        self.playerStats.nbrTreasuresHuntsDone += 1
        self.onPlayerUpdate(event)
    
    def onLostKamasByBankOpen(self, event, amount):
        self.playerStats.kamasSpentOpeningBank += int(amount)
        self.onPlayerUpdate(event)
        
    def onTeleportWithZaap(self, event):
        self.playerStats.numberOfTeleports += 1
        self.onPlayerUpdate(event)
        
    def onKamasGained(self, event, amount):
        self.playerStats.earnedKamas += int(amount)
        self.onPlayerUpdate(event)

    def onKamasTeleport(self, event, amount):
        self.playerStats.kamasSpentTeleporting += int(amount)
        self.onPlayerUpdate(event)
        
    def onKamasUpdate(self, event, totalKamas):
        Logger().debug(f"Player kamas updated : {totalKamas}")
        if self.initial_kamas is None:
            self.initial_kamas = totalKamas
        else:
            self.playerStats.earnedKamas = totalKamas - self.initial_kamas
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
        self.playerStats.currentLevel = newLevel
        self.onPlayerUpdate(event)
                                        
    def onItemObtained(self, event, iw, qty):
        HaapiEventsManager().sendRandomEvent()
        if iw.objectGID not in ClassicTreasureHunt.CHESTS_GUID:
            averageKamasWon = (
                Kernel().averagePricesFrame.getItemAveragePrice(iw.objectGID) * qty
            )
            Logger().debug(f"Average kamas won from item: {averageKamasWon}")
            self.playerStats.estimatedKamasWon += averageKamasWon
        self.playerStats.add_item_gained(iw.objectGID, qty)
        self.onPlayerUpdate(event)

    def onObjectAdded(self, event, iw):
        HaapiEventsManager().sendRandomEvent()
        if iw.objectGID not in ClassicTreasureHunt.CHESTS_GUID:
            averageKamasWon = (
                Kernel().averagePricesFrame.getItemAveragePrice(iw.objectGID) * iw.quantity
            )
            Logger().debug(f"Average kamas won from item: {averageKamasWon}")
            self.playerStats.estimatedKamasWon += averageKamasWon
        self.playerStats.add_item_gained(iw.objectGID, iw.quantity)
        self.onPlayerUpdate(event)

    def onJobExperience(self, event, oldJobXp, jobExp: JobExperience):
        Logger().info(f"Job {jobExp.jobId} has gained {jobExp.jobXP} xp")

    def onMapDataProcessed(self, event, mapId):
        HaapiEventsManager().sendRandomEvent()
        self.playerStats.currentLevel = PlayedCharacterManager().limitedLevel
        self.playerStats.currentMapId = mapId
        self.playerStats.add_visited_map(mapId)
        self.onPlayerUpdate(event)
    
    def onAchievementFinished(self, event, achievement):
        if PlayedCharacterManager().isFighting:
            return
        message = AchievementRewardRequestMessage()
        message.init(achievement.id)
        ConnectionsHandler().send(message)
        HaapiEventsManager().sendRandomEvent()
        return True

    def onFight(self, event):
        self.playerStats.nbrFightsDone += 1
        self.onPlayerUpdate(event)

    def get_dict_diff(old_dict, new_dict):
        """
        Get the difference between two dictionaries.
        Returns a dictionary with only the changed keys and their new values.
        """
        set_old = set(old_dict.items())
        set_new = set(new_dict.items())
        
        # Get symmetric difference
        diff_set = set_old ^ set_new
        
        # Convert back to dictionary, only for new values
        diff_dict = {key: value for key, value in diff_set if key in new_dict}
        
        return diff_dict

    def onPlayerUpdate(self, event):
        serialized_stats = self.playerStats.model_dump()
        if self._oldStats is not None:
            data_to_send = self.get_dict_diff(serialized_stats, self._oldStats)
        else:
            data_to_send = serialized_stats
        self._oldStats = serialized_stats
        if self.update_listeners:
            for listener in self.update_listeners:
                BenchmarkTimer(0.1, lambda: listener(event, data_to_send)).start()