from typing import TYPE_CHECKING

from pyd2bot.logic.roleplay.frames.BotAutoTripFrame import BotAutoTripFrame
from pyd2bot.logic.roleplay.messages.AutoTripEndedMessage import AutoTripEndedMessage
from pyd2bot.misc.Localizer import Localizer
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
        self._waitingForMapData = False
        if PlayerLifeStatusEnum(PlayedCharacterManager().state) == PlayerLifeStatusEnum.STATUS_PHANTOM:
            self.phenixMapId = Localizer.getPhenixMapId()
            Kernel().worker.addFrame(BotAutoTripFrame(self.phenixMapId))
        elif PlayedCharacterManager().state == PlayerLifeStatusEnum.STATUS_TOMBSTONE:
            self.releaseSoul()
        return True

    def pulled(self) -> bool:
        return True

    @property
    def priority(self) -> int:
        return Priority.HIGH

    def process(self, msg: Message) -> bool:

        if isinstance(msg, AutoTripEndedMessage):
            self.clickOnPhenix()
            return True

        elif isinstance(msg, GameRolePlayPlayerLifeStatusMessage):
            if PlayedCharacterManager().state == PlayerLifeStatusEnum.STATUS_PHANTOM:
                # state changed from tomb to phantome
                self._waitingForMapData = True
            else:
                Logger().info("Player is not in phantom state will renmove the phenix frame")
                Kernel().worker.removeFrame(self)
            return False

        elif isinstance(msg, MapComplementaryInformationsDataMessage):
            if self._waitingForMapData:
                self.phenixMapId = Localizer.getPhenixMapId()
                Kernel().worker.addFrame(BotAutoTripFrame(self.phenixMapId))
                self._waitingForMapData = False
            return False

    def clickOnPhenix(self):
        interactives: "RoleplayInteractivesFrame" = Kernel().worker.getFrame("RoleplayInteractivesFrame")
        if interactives:
            reviveSkill = interactives.getReviveIe()
            interactives.skillClicked(reviveSkill)

    def releaseSoul(self):
        grpfsrmmsg = GameRolePlayFreeSoulRequestMessage()
        ConnectionsHandler().send(grpfsrmmsg)
