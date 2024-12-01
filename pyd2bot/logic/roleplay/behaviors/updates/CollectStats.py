import time
from pyd2bot.data.models import PlayerStats
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.misc.BotEventsManager import BotEventsManager
from pydofus2.com.ankamagames.atouin.HaapiEventsManager import \
    HaapiEventsManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.enums.FightOutcomeEnum import FightOutcomeEnum
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
        self.sessionStats = saved_stats if saved_stats else PlayerStats()
        self._old_saved_kamas = None
        if listeners is None:
            listeners = []
        self.update_listeners = listeners
        self._last_fight_outcome_ts = None

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
                (KernelEvent.BankInventoryContent, self.onBankContent, {}),
                (KernelEvent.InventoryWeightUpdate, self.onWeightUpdate, {}),
                (KernelEvent.FightOutcomeForPlayer, self.onFightOutcome, {}),
                (KernelEvent.PlayerDied, self.onPlayerDied, {})
            ]
        )
        BotEventsManager().on(BotEventsManager.events.TimeToNextNap, self.onNapScheduled, originator=self)
        self.sessionStats.currentInventoryKamasBalance = InventoryManager().inventory.kamas
        self.onPlayerUpdate(KernelEvent.KamasUpdate)
        return True
    
    def onPlayerDied(self, event):
        self.sessionStats.nbrOfDeaths += 1
        self.onPlayerUpdate(event)

    def onFightOutcome(self, event, outcome: FightOutcomeEnum):
        current_time = time.time()
        
        # Guard condition: Skip if less than 20 seconds since last fight outcome
        if self._last_fight_outcome_ts is not None:
            time_since_last = current_time - self._last_fight_outcome_ts
            if time_since_last < 20:  # 20 seconds minimum between fight outcomes
                Logger().warning(f"Ignoring fight outcome, only {time_since_last:.2f} seconds since last one")
                return
        
        self._last_fight_outcome_ts = current_time
        
        if outcome == FightOutcomeEnum.RESULT_LOST:
            self.sessionStats.nbrFightsLost += 1
            self.onPlayerUpdate(event)

    def onWeightUpdate(self, event, lastInventoryWeight, inventoryWeight, weightMax):
        self.sessionStats.currentInventoryWeightPercent = round(100 * inventoryWeight / weightMax, 2)
        self.onPlayerUpdate(event)
        
    def onBankContent(self, event, objects, kamas):
        self.sessionStats.currentBankKamasBalance = kamas
        self.onPlayerUpdate(event)

    def onNapScheduled(self, event, nap_timeout):
        self.sessionStats.nextPauseTimestamp = time.time() + nap_timeout
        self.onPlayerUpdate(event)

    def addHandler(self, callback):
        self.update_listeners.append(callback)
    
    def removeHandler(self, callback):
        self.update_listeners.remove(callback)

    def onKamasSpentOnSellTax(self, event, gid, qty, amount):
        self.sessionStats.kamasSpentOnTaxes += amount
        self.onPlayerUpdate(event)
        
    def onItemSold(self, event, gid, qty, amount):
        self.sessionStats.kamasEarnedSelling += amount
        self.onPlayerUpdate(event)

    def onHuntFinished(self, event, questType):
        self.sessionStats.nbrTreasuresHuntsDone += 1
        self.onPlayerUpdate(event)
    
    def onLostKamasByBankOpen(self, event, amount):
        self.sessionStats.kamasSpentOpeningBank += int(amount)
        self.onPlayerUpdate(event)
        
    def onTeleportWithZaap(self, event):
        self.sessionStats.numberOfTeleports += 1
        self.onPlayerUpdate(event)
        
    def onKamasGained(self, event, amount):
        self.sessionStats.earnedKamas += int(amount)
        self.onPlayerUpdate(event)

    def onKamasTeleport(self, event, amount):
        self.sessionStats.kamasSpentTeleporting += int(amount)
        self.onPlayerUpdate(event)
        
    def onKamasUpdate(self, event, totalKamas):
        Logger().debug(f"Player kamas updated : {totalKamas}")
        if self._old_saved_kamas is None:
            self._old_saved_kamas = totalKamas
        else:
            self.sessionStats.earnedKamas = totalKamas - self._old_saved_kamas
            self.sessionStats.currentInventoryKamasBalance = totalKamas
            self.onPlayerUpdate(event)

    def onJobLevelUp(self, event, jobId, jobName, lastJobLevel, newLevel, podsBonus):
        HaapiEventsManager().sendProfessionsOpenEvent()
        Kernel().worker.terminated.wait(2)
        if jobId not in self.sessionStats.earnedJobLevels:
            self.sessionStats.earnedJobLevels[jobId] = 0
        self.sessionStats.earnedJobLevels[jobId] += newLevel - lastJobLevel
        self.onPlayerUpdate(event)

    def onPlayerLevelUp(self, event, previousLevel, newLevel):
        HaapiEventsManager().sendInventoryOpenEvent()
        Kernel().worker.terminated.wait(2)
        HaapiEventsManager().sendSocialOpenEvent()
        Kernel().worker.terminated.wait(2)
        self.sessionStats.earnedLevels += newLevel - previousLevel
        self.sessionStats.currentLevel = newLevel
        self.onPlayerUpdate(event)

    def onObjectAdded(self, event, gid: int, qty:int, average_kamas: int):
        self.sessionStats.estimatedKamasWon += average_kamas
        self.sessionStats.add_item_gained(gid, qty)
        self.onPlayerUpdate(event)

    def onJobExperience(self, event, oldJobXp, jobExp: JobExperience):
        Logger().info(f"Job {jobExp.jobId} has gained {jobExp.jobXP} xp")

    def onMapDataProcessed(self, event, mapId):
        HaapiEventsManager().sendRandomEvent()
        self.sessionStats.currentLevel = PlayedCharacterManager().limitedLevel
        self.sessionStats.currentMapId = mapId
        self.sessionStats.add_visited_map(mapId)
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
        self.sessionStats.nbrFightsDone += 1
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
        serialized_stats = self.sessionStats.model_dump()
        if self._oldStats is not None:
            data_to_send = self.get_dict_diff(self._oldStats, serialized_stats)
        else:
            data_to_send = serialized_stats
        self._oldStats = serialized_stats
        if self.update_listeners:
            for listener in self.update_listeners:
                DeferQueue.defer(lambda: listener(event, data_to_send))