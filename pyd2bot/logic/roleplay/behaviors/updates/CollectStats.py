from pyd2bot.data.models import PlayerStats
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
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
from pydofus2.com.ankamagames.jerakine.benchmark.DifferQueue import DeferQueue
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class CollectStats(AbstractBehavior):
    IS_BACKGROUND_TASK = True
    
    def __init__(self, listeners: list[callable]=None, saved_stats: PlayerStats=None):
        super().__init__()
        self._oldStats = None
        self.playerStats = saved_stats if saved_stats else PlayerStats()
        self.initial_kamas = None
        if listeners is None:
            listeners = []
        self.update_listeners = listeners

    def run(self) -> bool:
        self.on_multiple(
            [
                (KernelEvent.PlayerLeveledUp, self.onPlayerLevelUp, {}), 
                (KernelEvent.AchievementFinished, self.onAchievementFinished, {}),
                (KernelEvent.ObjectObtainedInFarm, self.onObjectAdded, {}),
                (KernelEvent.MapDataProcessed, self.onMapDataProcessed, {}),
                (KernelEvent.JobLevelUp, self.onJobLevelUp, {}),
                (KernelEvent.JobExperienceUpdate, self.onJobExperience, {}),
                (KernelEvent.KamasUpdate, self.onKamasUpdate, {}),
                (KernelEvent.FightStarted, self.onFight, {}),
                (KernelEvent.KamasLostFromTeleport, self.onKamasTeleport, {}),
                (KernelEvent.KamasGained, self.onKamasGained, {}),
                (KernelEvent.TreasureHuntFinished, self.onHuntFinished, {}),
                (KernelEvent.ZAAP_TELEPORT, self.onTeleportWithZaap, {}),
                (KernelEvent.KamasLostFromBankOpen, self.onLostKamasByBankOpen, {}),
                (KernelEvent.ItemSold, self.onItemSold, {}),
                (KernelEvent.KamasSpentOnSellTax, self.onKamasSpentOnSellTax, {}),
            ]
        )
        return True
    
    def addHandler(self, callback):
        self.update_listeners.append(callback)
    
    def removeHandler(self, callback):
        self.update_listeners.remove(callback)

    def onKamasSpentOnSellTax(self, event, gid, qty, amount):
        self.playerStats.kamasSpentOnTaxes += amount
        self.onPlayerUpdate(event)
        
    def onItemSold(self, event, gid, qty, amount):
        self.playerStats.kamasEarnedSelling += amount
        self.onPlayerUpdate(event)

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

    def onObjectAdded(self, event, gid: int, qty:int, average_kamas: int):
        self.playerStats.estimatedKamasWon += average_kamas
        self.playerStats.add_item_gained(gid, qty)
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

    def flatten_dict(self, d, parent_key='', sep='.'):
        """
        Flatten a nested dictionary. Keys will be concatenated with `sep`.
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self.flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    @classmethod
    def get_dict_diff(cls, old_dict, new_dict):
        """
        Get the difference between two dictionaries.
        Returns a dictionary with only the changed keys and their new values.
        """
        # Identify keys present in the new dict that are not in the old dict or have different values
        diff_dict = {k: v for k, v in new_dict.items() if k not in old_dict or old_dict[k] != v}
        return diff_dict

    def onPlayerUpdate(self, event):
        serialized_stats = self.playerStats.model_dump()
        if self._oldStats is not None:
            data_to_send = self.get_dict_diff(self._oldStats, serialized_stats)
        else:
            data_to_send = serialized_stats
        self._oldStats = serialized_stats
        if self.update_listeners:
            for listener in self.update_listeners:
                DeferQueue.defer(lambda: listener(event, data_to_send))