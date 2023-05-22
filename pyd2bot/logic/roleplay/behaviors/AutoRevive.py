from typing import TYPE_CHECKING

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.AutoTrip import AutoTrip
from pyd2bot.logic.roleplay.behaviors.UseSkill import UseSkill
from pyd2bot.misc.Localizer import Localizer
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import (
    KernelEvent, KernelEventsManager)
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.enums.PlayerLifeStatusEnum import \
    PlayerLifeStatusEnum
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.death.GameRolePlayFreeSoulRequestMessage import \
    GameRolePlayFreeSoulRequestMessage
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import \
    BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayInteractivesFrame import \
        RoleplayInteractivesFrame

class AutoRevive(AbstractBehavior):

    def __init__(self) -> None:
        super().__init__()
        self.requestTimer = None

    def run(self) -> bool:
        Logger().info("[PhenixAutorevive] Started.")
        if not PlayedCharacterManager().currentMap:
            return KernelEventsManager().onceMapProcessed(self.start, originator=self)
        KernelEventsManager().on(KernelEvent.PLAYER_STATE_CHANGED, self.onPlayerStateChange)
        if PlayerLifeStatusEnum(PlayedCharacterManager().state) == PlayerLifeStatusEnum.STATUS_PHANTOM:
            AutoTrip().start(Localizer.phenixMapId(), 1, callback=self.onPhenixMapReached, parent=self)
        elif PlayerLifeStatusEnum(PlayedCharacterManager().state) == PlayerLifeStatusEnum.STATUS_TOMBSTONE:
            KernelEventsManager().onceMapProcessed(self.onCimetaryMapLoaded, originator=self)
            self.releaseSoulRequest()

    def onPlayerStateChange(self, event, playerState: PlayerLifeStatusEnum):
        if playerState == PlayerLifeStatusEnum.STATUS_PHANTOM:
            Logger().info(f"[PhenixAutorevive] Player saoul released wating for cimetary map to load.")
        elif playerState == PlayerLifeStatusEnum.STATUS_ALIVE_AND_KICKING:
            Logger().info("[PhenixAutorevive] Player is alive and kicking")
            KernelEventsManager().remove_listener(KernelEvent.PLAYER_STATE_CHANGED, self.onPlayerStateChange)
            self.finish(True, None)

    def onCimetaryMapLoaded(self, event_id=None):
        Logger().debug(f"[PhenixAutorevive] Cimetary map loaded.")
        if self.requestTimer:
            self.requestTimer.cancel()
        KernelEventsManager().remove_listener(KernelEvent.MAPPROCESSED, self.onCimetaryMapLoaded)
        AutoTrip().start(Localizer.phenixMapId(), 1, callback=self.onPhenixMapReached, parent=self)

    def onPhenixMapReached(self, status, error):
        if error:
            return self.finish(status, error)
        interactives: "RoleplayInteractivesFrame" = Kernel().worker.getFrameByName("RoleplayInteractivesFrame")
        if interactives:
            reviveSkill = interactives.getReviveIe()
            def onPhenixSkillUsed(status, error):
                Logger().info("Phenix revive skill used")
            UseSkill().start(reviveSkill, waitForSkillUsed=False, callback=onPhenixSkillUsed, parent=self)
        else:
            KernelEventsManager().onceFramePushed("RoleplayInteractivesFrame", self.onPhenixMapReached, originator=self)

    def releaseSoulRequest(self):
        def ontimeout():
            self.finish(False, "[PhenixAutorevive] Player release saoul request timeout!")
        self.requestTimer = BenchmarkTimer(20, ontimeout)
        self.requestTimer.start()
        ConnectionsHandler().send(GameRolePlayFreeSoulRequestMessage())
