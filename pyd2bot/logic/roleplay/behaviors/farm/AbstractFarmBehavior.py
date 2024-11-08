import os
import threading
from time import perf_counter
from typing import Any, TYPE_CHECKING

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.movement.AutoTrip import AutoTrip
from pyd2bot.logic.roleplay.behaviors.movement.ChangeMap import ChangeMap
from pyd2bot.logic.roleplay.behaviors.skill.UseSkill import UseSkill
from pyd2bot.farmPaths.AbstractFarmPath import AbstractFarmPath
from pyd2bot.farmPaths.RandomAreaFarmPath import NoTransitionFound
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import ItemWrapper
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.types.MovementFailError import MovementFailError
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.GuildInformations import GuildInformations
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.job.JobExperience import JobExperience
from pydofus2.com.ankamagames.dofus.uiApi.PlayedCharacterApi import PlayedCharacterApi
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
if TYPE_CHECKING:
    pass

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
        self.on_multiple(
            [
                (KernelEvent.FightStarted, self.onFight, {}),
                (KernelEvent.PlayerStateChanged, self.onPlayerStateChange, {}),
                (KernelEvent.JobExperienceUpdate, self.onJobExperience, {}),
                (KernelEvent.InventoryWeightUpdate, self.onInventoryWeightUpdate, {}),
                (KernelEvent.ObjectAdded, self.onObjectAdded, {}),
                (KernelEvent.JobLevelUp, self.onJobLevelUp, {}),
                (KernelEvent.PartyInvited, self.onPartyInvited, {}),
                (KernelEvent.GuildInvited, self.onGuildInvited, {}),
            ]
        )

    def onPartyInvited(self, event, partyId, partyType, fromId, fromName):
        pass

    def onGuildInvited(self, event, guildInfo: GuildInformations, recruterName: str):
        pass

    def onJobLevelUp(self, event, jobId: int, jobName: str, lastJobLevel: int, newLevel: int, podsBonus: int):
        pass

    def onObjectAdded(self, event, iw: ItemWrapper, added_quantity: int):
        pass

    def onReturnToLastVertex(self, code, err):
        if err:
            if code == MovementFailError.PLAYER_IS_DEAD:
                Logger().warning(f"Player is dead.")
                return self.autoRevive(callback=self._on_resurrection)
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

    def onInventoryWeightUpdate(self, event, lastWeight, weight, weightMax):
        pass

    def _on_back_to_farm_path(self, code, error):
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
            elif code in [
                UseSkill.USE_ERROR,
                AutoTrip.NO_PATH_FOUND,
                ChangeMap.INVALID_TRANSITION,
                ChangeMap.NEED_QUEST,
            ]:
                Logger().warning(f"Player tried navigating using invalid edge ({error}), edge will be forbidden")
                self.forbiddenEdges.add(self._currEdge)
                return self._move_to_next_step()
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

    def _move_to_next_step(self):
        if not self.running.is_set():
            return
        try:
            self._currEdge = self.path.getNextEdge(self.forbiddenEdges, onlyNonRecent=True)
        except NoTransitionFound:
            Logger().error(f"No next vertex found in path, player is stuck!")
            if PlayedCharacterManager().currVertex in self.path:
                self.finish(self.PLAYER_STUCK, "Player is stuck in farm path without next vertex!")
            else:
                self._on_out_of_path()
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

    def _on_out_of_path(self):
        Logger().warning(f"Bot is out of farm path, searching path to previous vertex...")
        if not PlayedCharacterManager().currVertex:
            Logger().warning("Bot vertex not loaded yet!, delaying return to path after Map is processed...")
            return self.once_map_processed(callback=self._on_out_of_path)
        self.travel_using_zaap(
            self.path.startVertex.mapId,
            self.path.startVertex.zoneId,
            withSaveZaap=False,
            callback=self._on_back_to_farm_path,
        )

    def _on_inventory_unloaded(self, code, err):
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
        self.once(KernelEvent.RoleplayStarted, self._on_roleplay_started_after_fight)

    def _on_riding_mount(self, code, err):
        if err:
            Logger().error(f"Error[{code}] while riding mount: {err}")
            self._deactivate_riding = True
        self.main()

    def _on_resurrection(self, code, error):
        if error:
            return self.finish(code, f"Error [{code}] while auto-reviving player: {error}")
        Logger().debug(f"Bot back on form, traveling to last memorized vertex {self.currentVertex}")
        if self.initialized:
            self.travel_using_zaap(
                self.currentVertex.mapId,
                self.currentVertex.zoneId,
                True,
                callback=self._on_back_to_previous_position,
            )
        else:
            self.main()

    def _on_back_to_previous_position(self, code, err):
        if err:
            if code == AutoTrip.PLAYER_IN_COMBAT:
                Logger().error("Player in combat")
                return
            elif code == AutoTrip.NO_PATH_FOUND:
                Logger().error("No path found to last map!")
                return self._on_out_of_path()
            return KernelEventsManager().send(KernelEvent.ClientRestart, err)
        Logger().debug(f"Player got back to last map after combat")
        self.main()

    def _on_roleplay_started_after_fight(self, event=None):
        Logger().debug(f"Player ended fight and started roleplay")
        self.initListeners()
        self.inFight = False

        def onRolePlayMapLoaded():
            if PlayedCharacterManager().isDead():
                Logger().warning(f"Player is dead.")
                return self.autoRevive(callback=self._on_resurrection)
            self.main()

        self.once_map_processed(onRolePlayMapLoaded)

    def _on_full_pods(self):
        self.unload_in_bank(callback=self._on_inventory_unloaded)
    
    def main(self, event_code=None, error=None):
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
            Logger().warning("Stopping farm loop because the farmer entered a fight!")
            return

        if PlayedCharacterManager().isDead():
            Logger().warning(f"Player is dead.")
            return self.autoRevive(callback=self._on_resurrection)

        if not self._deactivate_riding and PlayedCharacterApi.canRideMount():
            Logger().info(f"Mounting {PlayedCharacterManager().mount.name} ...")
            return self.toggle_ride_mount(wanted_ride_state=True, callback=self._on_riding_mount)

        if PlayedCharacterManager().isPodsFull():
            Logger().warning(f"Inventory is almost full will trigger retrieve sell and update items workflow ...")
            return self._on_full_pods()

        if self._specific_checks():
            return
        
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
            return self._on_out_of_path()

        self.makeAction()

    def makeAction(self):
        """
        This method is called each time the main loop is called.
        It should be overridden by subclasses to implement the behavior.
        The default implementation is to collect the nearest resource.
        """
        Logger().warning("No make action behavior implemented!")
    
    def _specific_checks(self):
        return False
