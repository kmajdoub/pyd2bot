import os
from time import perf_counter
from typing import Any

from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.movement.AutoTrip import AutoTrip
from pyd2bot.logic.roleplay.behaviors.movement.ChangeMap import ChangeMap
from pyd2bot.logic.roleplay.behaviors.skill.UseSkill import UseSkill
from pyd2bot.models.farmPaths.AbstractFarmPath import AbstractFarmPath
from pyd2bot.models.farmPaths.RandomAreaFarmPath import NoTransitionFound
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import \
    ItemWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import \
    PlayerManager
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
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

CURR_DIR = os.path.dirname(os.path.abspath(__file__))


class AbstractFarmBehavior(AbstractBehavior):
    path: AbstractFarmPath
    currentTarget: Any = None

    def __init__(self, timeout=None):
        self.timeout = timeout
        self.currentVertex: Vertex = None
        self.forbidenActions = set()
        self.forbidenEdges = set()
        self._currEdge = None
        super().__init__()

    def run(self, *args, **kwargs):
        self.on(KernelEvent.FightStarted, self.onFight)
        self.on(KernelEvent.PlayerStateChanged, self.onPlayerStateChange)
        self.on(KernelEvent.JobExperienceUpdate, self.onJobExperience)
        self.on(KernelEvent.InventoryWeightUpdate, self.onInventoryWeightUpdate)
        self.on(KernelEvent.ObtainedItem, self.onObtainedItem)
        self.on(KernelEvent.ObjectAdded, self.onObjectAdded)
        self.on(KernelEvent.JobLevelUp, self.onJobLevelUp)
        self.on(KernelEvent.PartyInvited, self.onPartyInvited)
        self.on(KernelEvent.GuildInvited, self.onGuildInvited)
        self.inFight = False
        self.initialized = False
        self.startTime = perf_counter()
        self.init(*args, **kwargs)
        self.main()

    def onPartyInvited(self, event, partyId, partyType, fromId, fromName):
        pass
        
    def onGuildInvited(self, event, guildInfo: GuildInformations, recruterName):
        pass
        
    def onJobLevelUp(self, event, jobId, jobName, lastJobLevel, newLevel, podsBonus):
        pass

    def onObjectAdded(self, event, iw: ItemWrapper):
        pass

    def onReturnToLastvertex(self, code, err):
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
            return self.send(
                KernelEvent.ClientShutdown,
                f"Error while moving to farm path [{code}]: %s." % error,
            )
        Logger().debug(f"Player got back inside farm area")
        self.main()

    def onNextVertexReached(self, code, error):
        if error:
            if code == MovementFailError.PLAYER_IS_DEAD:
                return self.send(
                    KernelEvent.ClientShutdown, f"Tried to move to next path vertex while Player is dead!"
                )
            if code == ChangeMap.LANDED_ON_WRONG_MAP:
                Logger().warning(f"Player landed on the wrong map while moving to next path Vertex!")
            elif code in [UseSkill.USE_ERROR, AutoTrip.NO_PATH_FOUND, ChangeMap.INVALID_TRANSITION, ChangeMap.NEED_QUEST]:
                Logger().warning(f"Player tried navigating using invalid edge ({error}), edge will be forbiden")
                self.forbidenEdges.add(self._currEdge)
                return self.moveToNextStep()
            else:
                return self.send(
                    KernelEvent.ClientShutdown,
                    "Error while moving to next step: %s." % error,
                )
        Logger().debug(f"Player moved to next vertex")
        if not PlayedCharacterManager().isInFight:
            self.currentVertex = self.path.currentVertex
        if self._currEdge:
            self.path.lastVisited[self._currEdge] = perf_counter()
        self.forbidenActions = set()
        self.main()

    def moveToNextStep(self):
        if not self.running.is_set():
            return
        try:
            self._currEdge = self.path.getNextVertex(self.forbidenEdges, onlyNonRecent=True)
        except NoTransitionFound:
            Logger().error(f"No next vertex found in path, player is stuck!")
            if PlayedCharacterManager().currVertex in self.path:
                return KernelEventsManager().send(
                    KernelEvent.ClientRestart, "Player is stuck in farm path without next vertex!"
                )
            return self.onBotOutOfFarmPath()
        self.changeMap(
            edge=self._currEdge,
            dstMapId=self._currEdge.dst.mapId,
            callback=self.onNextVertexReached,
        )

    def onBotOutOfFarmPath(self):
        Logger().warning(f"Bot is out of farm path, searching path to last vertex...")
        # dst_vertex, dist = self.path.findClosestMap()
        # Logger().debug(f"Found closest map {dst_vertex} at distance {dist} from current map")
        self.autotripUseZaap(
            self.path.startVertex.mapId,
            self.path.startVertex.zoneId,
            withSaveZaap=False,
            callback=self.onGotBackInsideFarmArea,
        )

    def onBotUnloaded(self, code, err):
        if err:
            return self.send(KernelEvent.ClientShutdown, f"Error while unloading: {err}")
        self.main()

    def onResourceCollectEnd(self, code, error, iePosition=None):
        raise NotImplementedError()

    def onFight(self, event=None):
        Logger().warning(f"Player entered in a fight.")
        self.inFight = True
        self.stopChilds()
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

    def onPlayerRidingMount(self, event, riding):
        if not riding:
            Logger().error(f"Player dismounted when asked to mount!")
        self.autotripUseZaap(
            self.currentVertex.mapId,
            self.currentVertex.zoneId,
            True,
            callback=self.main,
        )

    def onRevived(self, code, error):
        if error:
            KernelEventsManager().send(
                KernelEvent.ClientShutdown, f"Error [{code}] while auto-reviving player: {error}"
            )
        Logger().debug(f"Bot back on form, autotravelling to last memorized vertex {self.currentVertex}")
        if self.initialized:
            self.autotripUseZaap(
                self.currentVertex.mapId,
                self.currentVertex.zoneId,
                True,
                callback=self.ongotBackToLastMap,
            )
        else:
            self.main()

    def ongotBackToLastMap(self, code, err):
        if err:
            if code == AutoTrip.PLAYER_IN_COMBAT:
                Logger().error("Player in combat")
                return
            elif AutoTrip.NO_PATH_FOUND:
                Logger().error("No path found to last map!")
                return self.onBotOutOfFarmPath()
            return KernelEventsManager().send(KernelEvent.ClientRestart, err)
        Logger().debug(f"Player got back to last map after combat")
        self.main()

    def onRoleplayAfterFight(self, event=None):
        Logger().debug(f"Player ended fight and started roleplay")
        self.inFight = False
        def onRolePlayMapLoaded():
            if PlayedCharacterManager().isDead():
                Logger().warning(f"Player is dead.")
                return self.autoRevive(callback=self.onRevived)

            self.main()

        self.onceMapProcessed(onRolePlayMapLoaded)

    def main(self, event=None, error=None):
        Logger().debug(f"Farmer main loop called")
        if not self.running.is_set():
            Logger().error(f"Is not running!")
            return
        if self.timeout and perf_counter() - self.startTime > self.timeout:
            Logger().warning(f"Ending Behavior for reason : Timeout reached")
            return self.finish(True, None)
        if PlayedCharacterManager().currentMap is None:
            return self.onceMapProcessed(callback=self.main)
        if self.inFight:
            return
        if PlayedCharacterManager().isDead():
            Logger().warning(f"Player is dead.")
            return self.autoRevive(callback=self.onRevived)
        if (
            not PlayerManager().isBasicAccount()
            and PlayedCharacterApi.getMount()
            and not PlayedCharacterApi.isRiding()
        ):
            Logger().info(f"Mounting {PlayedCharacterManager().mount.name}")
            KernelEventsManager().once(KernelEvent.MountRiding, self.main)
            return Kernel().mountFrame.mountToggleRidingRequest()
        if PlayedCharacterManager().isPodsFull():
            Logger().warning(f"Inventory is almost full will trigger auto unload ...")
            if PlayedCharacterManager().limitedLevel < 10 and BotConfig().unloadInBank:
                Logger().warning(f"Player level is too low to unload in bank, ending behavior")
                return KernelEventsManager().send(
                    KernelEvent.ClientShutdown, "Player level is too low to unload in bank"
                )
            return self.unloadInBank(callback=self.onBotUnloaded)
        if not self.initialized:
            Logger().debug(f"Initializing behavior...")
            self.initialized = True
            if self.currentVertex:
                Logger().debug(f"Traveling to the memorized current vertex...")
                return self.autotripUseZaap(
                    self.currentVertex.mapId, self.currentVertex.zoneId, True, callback=self.onReturnToLastvertex
                )
            else:
                self.currentVertex = self.path.currentVertex
        if PlayedCharacterManager().currVertex not in self.path:
            Logger().debug(f"Bot is out of farming area")
            return self.onBotOutOfFarmPath()
        self.makeAction()

    def makeAction(self):
        """
        This method is called each time the main loop is called.
        It should be overriden by subclasses to implement the behavior.
        The default implementation is to collect the nearest resource.
        """
        pass
