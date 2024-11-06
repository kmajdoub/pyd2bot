import os
import threading
from time import perf_counter
from typing import Any

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.bidhouse.SellItemsFromBag import SellItemsFromBag
from pyd2bot.logic.roleplay.behaviors.movement.AutoTrip import AutoTrip
from pyd2bot.logic.roleplay.behaviors.movement.ChangeMap import ChangeMap
from pyd2bot.logic.roleplay.behaviors.skill.UseSkill import UseSkill
from pyd2bot.farmPaths.AbstractFarmPath import AbstractFarmPath
from pyd2bot.farmPaths.RandomAreaFarmPath import NoTransitionFound
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import \
    ItemWrapper
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.types.MovementFailError import \
    MovementFailError
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import \
    Vertex
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.GuildInformations import \
    GuildInformations
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.job.JobExperience import \
    JobExperience
from pydofus2.com.ankamagames.dofus.uiApi.PlayedCharacterApi import \
    PlayedCharacterApi
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

CURR_DIR = os.path.dirname(os.path.abspath(__file__))


class AbstractFarmBehavior(AbstractBehavior):
    path: AbstractFarmPath
    currentTarget: Any = None
    JOIN_PATH_FAILED = 909988
    PLAYER_STUCK = 909989

    def __init__(self, timeout=None):
        self.timeout = timeout
        self.currentVertex: Vertex = None
        self.forbiddenActions = set()
        self.forbiddenEdges = set()
        self._currEdge = None
        self._deactivate_riding = False
        self._stop_sig = threading.Event()
        self._moving_to_next_step = False
        super().__init__()


    def stop(self):
        self._stop_sig.set()
        
    def run(self, *args, **kwargs):
        self.initListeners()
        self.inFight = False
        self.initialized = False
        self.startTime = perf_counter()
        self.init(*args, **kwargs)
        self.main()

    def initListeners(self):
        self.on(KernelEvent.FightStarted, self.onFight)
        self.on(KernelEvent.PlayerStateChanged, self.onPlayerStateChange)
        self.on(KernelEvent.JobExperienceUpdate, self.onJobExperience)
        self.on(KernelEvent.InventoryWeightUpdate, self.onInventoryWeightUpdate)
        self.on(KernelEvent.ObtainedItem, self.onObtainedItem)
        self.on(KernelEvent.ObjectAdded, self.onObjectAdded)
        self.on(KernelEvent.JobLevelUp, self.onJobLevelUp)
        self.on(KernelEvent.PartyInvited, self.onPartyInvited)
        self.on(KernelEvent.GuildInvited, self.onGuildInvited)
        
    def onPartyInvited(self, event, partyId, partyType, fromId, fromName):
        pass
        
    def onGuildInvited(self, event, guildInfo: GuildInformations, recruterName):
        pass
        
    def onJobLevelUp(self, event, jobId, jobName, lastJobLevel, newLevel, podsBonus):
        pass

    def onObjectAdded(self, event, iw: ItemWrapper):
        pass

    def onReturnToLastVertex(self, code, err):
        if err:
            if code == MovementFailError.PLAYER_IS_DEAD:
                Logger().warning(f"Player is dead.")
                return self.autoRevive(callback=self.onRevived)
            elif code == AutoTrip.PLAYER_IN_COMBAT:
                Logger().debug("Player in combat")
                return
            return self.finish(code, err)
        Logger().debug(f"Returned to last vertex")
        self.main()

    def init(self, *args, **kwargs):
        raise NotImplementedError()

    def onPlayerStateChange(self, event, state, phenixMapId):
        pass

    def onJobExperience(self, event, oldJobXp, jobExperience: JobExperience):
        pass

    def onObtainedItem(self, event, iw: ItemWrapper, qty):
        pass

    def onInventoryWeightUpdate(self, event, lastWeight, weight, weightMax):
        pass

    def onGotBackInsideFarmArea(self, code, error):
        if error:
            if code == 666:
                if ChangeMap().isRunning():
                    ChangeMap().stop()
                    self.main()
                    return
            return self.finish(self.JOIN_PATH_FAILED, f"Error while moving to farm path [{code}]: %s." % error)
        Logger().debug(f"Player got back inside farm area")
        self.main()

    def onNextVertexReached(self, code, error):
        if not self._moving_to_next_step:
            Logger().warning("Next vertex reached called but farmer is not waiting for vertex change!")
            return
        self._moving_to_next_step = False
        if error:
            if code == MovementFailError.PLAYER_IS_DEAD:
                return self.send(
                    KernelEvent.ClientShutdown, f"Tried to move to next path vertex while Player is dead!"
                )
            if code == ChangeMap.LANDED_ON_WRONG_MAP:
                Logger().warning(f"Player landed on the wrong map while moving to next path Vertex!")
            elif code in [UseSkill.USE_ERROR, AutoTrip.NO_PATH_FOUND, ChangeMap.INVALID_TRANSITION, ChangeMap.NEED_QUEST]:
                Logger().warning(f"Player tried navigating using invalid edge ({error}), edge will be forbidden")
                self.forbiddenEdges.add(self._currEdge)
                return self.moveToNextStep()
            else:
                return self.send(
                    KernelEvent.ClientRestart,
                    "Error while moving to next step: %s." % error,
                )
        if PlayedCharacterManager().isInFight:
            return
        Logger().debug(f"Player moved to next vertex")
        if not PlayedCharacterManager().isInFight:
            self.currentVertex = self.path.currentVertex
        if self._currEdge:
            self.path._lastVisited[self._currEdge] = perf_counter()
        self.forbiddenActions = set()
        self.main()

    def moveToNextStep(self):
        if not self.running.is_set():
            return
        try:
            self._currEdge = self.path.getNextEdge(self.forbiddenEdges, onlyNonRecent=True)
        except NoTransitionFound:
            Logger().error(f"No next vertex found in path, player is stuck!")
            if PlayedCharacterManager().currVertex in self.path:
                self.finish(self.PLAYER_STUCK, "Player is stuck in farm path without next vertex!")
            else:
                self.onBotOutOfFarmPath()
            return None
        Logger().debug("Will move to next vertex in farm path")
        
        if ChangeMap().isRunning():
            Logger().warning("Farmer found change map behavior already running!")
            self._moving_to_next_step = False
            ChangeMap().stop(True)

        self._moving_to_next_step = True
        self.changeMap(
            edge=self._currEdge,
            dstMapId=self._currEdge.dst.mapId,
            callback=self.onNextVertexReached,
        )
        return self._currEdge

    def onBotOutOfFarmPath(self):
        Logger().warning(f"Bot is out of farm path, searching path to last vertex...")
        if not PlayedCharacterManager().currVertex:
            Logger().warning("Bot vertex not loaded yet!, delaying return to path after Map is processed.")
            return self.once_map_processed(callback=self.onBotOutOfFarmPath)
        self.travel_using_zaap(
            self.path.startVertex.mapId,
            self.path.startVertex.zoneId,
            withSaveZaap=False,
            callback=self.onGotBackInsideFarmArea,
        )

    def onBotUnloaded(self, code, err):
        if err:
            return self.finish(code, f"Error while unloading: {err}")
        self.main()

    def onResourceCollectEnd(self, code, error, iePosition=None):
        raise NotImplementedError()

    def onFight(self, event=None):
        Logger().debug(f"Player entered in a fight.")
        self.inFight = True
        self._moving_to_next_step = False
        self.stopChildren()
        KernelEventsManager().clearAllByOrigin(self)
        self.once(KernelEvent.RoleplayStarted, self.onRoleplayAfterFight)

    def isCollectErrCodeRequireRefresh(self, code: int) -> bool:
        return False

    def isCollectErrRequireRestart(self, code: int) -> bool:
        return False

    def isCollectErrRequireShutdown(self, code):
        return False

    def collectCurrResource(self):
        raise NotImplementedError()

    def getResourcesTableHeaders(self) -> list[str]:
        raise NotImplementedError()

    def onPlayerRidingMount(self, code, err):
        if err:
            Logger().error(f"Error[{code}] while riding mount: {err}")
            self._deactivate_riding = True
        self.main()

    def onRevived(self, code, error):
        if error:
            return self.finish(code, f"Error [{code}] while auto-reviving player: {error}")
        Logger().debug(f"Bot back on form, traveling to last memorized vertex {self.currentVertex}")
        if self.initialized:
            self.travel_using_zaap(
                self.currentVertex.mapId,
                self.currentVertex.zoneId,
                True,
                callback=self.onBackToLastMap,
            )
        else:
            self.main()

    def onBackToLastMap(self, code, err):
        if err:
            if code == AutoTrip.PLAYER_IN_COMBAT:
                Logger().error("Player in combat")
                return
            elif code == AutoTrip.NO_PATH_FOUND:
                Logger().error("No path found to last map!")
                return self.onBotOutOfFarmPath()
            return KernelEventsManager().send(KernelEvent.ClientRestart, err)
        Logger().debug(f"Player got back to last map after combat")
        self.main()

    def onRoleplayAfterFight(self, event=None):
        Logger().debug(f"Player ended fight and started roleplay")
        self.initListeners()
        self.inFight = False
        def onRolePlayMapLoaded():
            if PlayedCharacterManager().isDead():
                Logger().warning(f"Player is dead.")
                return self.autoRevive(callback=self.onRevived)
            self.main()
        self.once_map_processed(onRolePlayMapLoaded)

    def _on_items_sold(self, code, error):
        if error:
            if code == SellItemsFromBag.ERROR_CODES.NO_MORE_SELL_SLOTS:
                return self.unload_in_bank(callback=self.onBotUnloaded)
        if PlayedCharacterManager().isPodsFull(0.6):
            return self.unload_in_bank(callback=self.onBotUnloaded)
        self.onBotUnloaded(code, error)
            
    def main(self, event=None, error=None):
        Logger().debug(f"Farmer main loop called")

        if self._stop_sig.is_set():
            Logger().warning("User wanted to stop farmer!")
            self.stopChildren(True)
            return self.finish(True, None)

        if not self.running.is_set():
            Logger().error(f"Is not running!")
            return

        if PlayedCharacterManager().currentMap is None:
            return self.once_map_processed(callback=self.main)

        if self.inFight:
            Logger().warning('Stopping farm loop because the farmer got in a fight!')
            return

        if PlayedCharacterManager().isDead():
            Logger().warning(f"Player is dead.")
            return self.autoRevive(callback=self.onRevived)

        if not self._deactivate_riding and PlayedCharacterApi.canRideMount():
            Logger().info(f"Mounting {PlayedCharacterManager().mount.name} ...")
            return self.toggleRideMount(wanted_ride_state=True, callback=self.onPlayerRidingMount)

        if PlayedCharacterManager().isPodsFull():
            Logger().warning(f"Inventory is almost full will trigger auto unload ...")
        #     return self.unloadInBank(callback=self.onBotUnloaded)
            PIWI_FEATHER_GIDS = [6900, 6902, 6898, 6899, 6903, 6897]
            items_gids = [(gid, 100) for gid in PIWI_FEATHER_GIDS]
            return self.sell_items(items_gids, callback=self._on_items_sold)
            
        if not self.initialized:
            Logger().debug(f"Initializing behavior...")
            self.initialized = True
            if self.currentVertex:
                Logger().debug(f"Traveling to the memorized current vertex...")
                return self.travel_using_zaap(
                    self.currentVertex.mapId, self.currentVertex.zoneId, True, callback=self.onReturnToLastVertex
                )
            else:
                self.currentVertex = self.path.currentVertex

        if self.timeout and perf_counter() - self.startTime > self.timeout:
            Logger().warning(f"Ending Behavior for reason : Timeout reached")
            return self.finish(True, None)

        if PlayedCharacterManager().currVertex not in self.path:
            Logger().debug(f"Bot is out of farming area")
            return self.onBotOutOfFarmPath()

        self.makeAction()

    def makeAction(self):
        """
        This method is called each time the main loop is called.
        It should be overridden by subclasses to implement the behavior.
        The default implementation is to collect the nearest resource.
        """
        Logger().warning("No make action behavior implemented!")
