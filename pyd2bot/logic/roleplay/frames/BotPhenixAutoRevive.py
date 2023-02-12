import threading
from typing import TYPE_CHECKING
from pyd2bot.apis.MoveAPI import MoveAPI
from pyd2bot.logic.roleplay.messages.PhenixAutoReviveEndedMessage import PhenixAutoReviveEndedMessage
from pyd2bot.misc.Localizer import Localizer
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.enums.PlayerLifeStatusEnum import PlayerLifeStatusEnum
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.death.GameRolePlayFreeSoulRequestMessage import (
    GameRolePlayFreeSoulRequestMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.death.GameRolePlayPlayerLifeStatusMessage import (
    GameRolePlayPlayerLifeStatusMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapComplementaryInformationsDataMessage import (
    MapComplementaryInformationsDataMessage,
)
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayInteractivesFrame import (
        RoleplayInteractivesFrame,
    )


class AutoReviveStateEnum:
    PHANTOME = 0
    SAOUL_RELEASED = 1
    WALING_TO_PHOENIX = 2
    REVIVED = 3


class BotPhenixAutoRevive(Frame):
    def __init__(self):
        super().__init__()

    def pushed(self) -> bool:
        Logger().info("[PhenixFrame] frame pushed.")
        self._waitingForMapData = threading.Event()
        if self.playerState == PlayerLifeStatusEnum.STATUS_PHANTOM:
            self.phenixMapId = Localizer.getPhenixMapId()
            MoveAPI.moveToMap(self.phenixMapId, self.clickOnPhenix)
        elif self.playerState == PlayerLifeStatusEnum.STATUS_TOMBSTONE:
            KernelEventsManager().onceFramePushed("BotPhenixAutoRevive", self.releaseSoul)
        return True

    def pulled(self) -> bool:
        return True

    @property
    def priority(self) -> int:
        return Priority.HIGH

    @property
    def playerState(self) -> PlayerLifeStatusEnum:
        return PlayerLifeStatusEnum(PlayedCharacterManager().state)
    
    def process(self, msg: Message) -> bool:

        if isinstance(msg, GameRolePlayPlayerLifeStatusMessage):
            if PlayerLifeStatusEnum(msg.state) == PlayerLifeStatusEnum.STATUS_PHANTOM:
                Logger().debug(f"[PhenixFrame] Player saoul released wating for cimetary map to load.")
                self._waitingForMapData.set()
            elif PlayerLifeStatusEnum(msg.state) == PlayerLifeStatusEnum.STATUS_ALIVE_AND_KICKING:
                Logger().info("[PhenixFrame] Player is not in phantom state anymore, will remove the phenix frame.")
                Kernel().worker.removeFrame(self)
                Kernel().worker.process(PhenixAutoReviveEndedMessage())
            return False

        elif isinstance(msg, MapComplementaryInformationsDataMessage):
            if self._waitingForMapData.is_set():
                Logger().debug(f"[PhenixFrame] Cimetary map loaded.")
                self.phenixMapId = Localizer.getPhenixMapId()
                MoveAPI.moveToMap(self.phenixMapId, self.clickOnPhenix)
                self._waitingForMapData.clear()
            return False

    def clickOnPhenix(self):
        interactives: "RoleplayInteractivesFrame" = Kernel().worker.getFrameByName("RoleplayInteractivesFrame")
        if interactives:
            reviveSkill = interactives.getReviveIe()
            interactives.skillClicked(reviveSkill)

    def releaseSoul(self):
        grpfsrmmsg = GameRolePlayFreeSoulRequestMessage()
        ConnectionsHandler().send(grpfsrmmsg)
