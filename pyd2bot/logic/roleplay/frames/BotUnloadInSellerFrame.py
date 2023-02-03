import threading
from enum import Enum
from typing import TYPE_CHECKING

from pyd2bot.logic.common.frames.BotRPCFrame import BotRPCFrame
from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.logic.roleplay.frames.BotAutoTripFrame import BotAutoTripFrame
from pyd2bot.logic.roleplay.frames.BotExchangeFrame import BotExchangeFrame, ExchangeDirectionEnum
from pyd2bot.logic.roleplay.messages.AutoTripEndedMessage import AutoTripEndedMessage
from pyd2bot.logic.roleplay.messages.ExchangeConcludedMessage import ExchangeConcludedMessage
from pyd2bot.logic.roleplay.messages.SellerCollectedGuestItemsMessage import SellerCollectedGuestItemsMessage
from pyd2bot.misc.Localizer import Localizer
from pyd2bot.misc.Watcher import Watcher
from pyd2bot.thriftServer.pyd2botService.ttypes import Character
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapComplementaryInformationsDataMessage import (
    MapComplementaryInformationsDataMessage,
)
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayEntitiesFrame import RoleplayEntitiesFrame


class UnloadInSellerStatesEnum(Enum):
    WAITING_FOR_MAP = -1
    IDLE = 0
    WALKING_TO_BANK = 1
    ISIDE_BANK = 2
    RETURNING_TO_START_POINT = 4
    WAITING_FOR_SELLER = 5
    IN_EXCHANGE_WITH_SELLER = 6


class BotUnloadInSellerFrame(Frame):
    PHENIX_MAPID = None

    def __init__(self, sellerInfos: Character, return_to_start=True):
        super().__init__()
        self.seller = sellerInfos
        self.return_to_start = return_to_start
        self.stopWaitingForSeller = threading.Event()

    def pushed(self) -> bool:
        Logger().debug("BotUnloadInSellerFrame pushed")
        self.state = UnloadInSellerStatesEnum.IDLE
        self.stopWaitingForSeller.clear()
        if PlayedCharacterManager().currentMap is not None:
            self.start()
        else:
            self.state = UnloadInSellerStatesEnum.WAITING_FOR_MAP
        return True

    def pulled(self) -> bool:
        Logger().debug("BotUnloadInSellerFrame pulled")
        self.stopWaitingForSeller.set()
        return True

    @property
    def priority(self) -> int:
        return Priority.VERY_LOW

    @property
    def entitiesFrame(self) -> "RoleplayEntitiesFrame":
        return Kernel().worker.getFrame("RoleplayEntitiesFrame")

    def waitForSellerToComme(self):
        self.stopWaitingForSeller.clear()
        while not self.stopWaitingForSeller.is_set():
            if self.entitiesFrame:
                if self.entitiesFrame.getEntityInfos(self.seller.id):
                    Logger().debug("Seller found in the bank map")
                    Kernel().worker.addFrame(BotExchangeFrame(ExchangeDirectionEnum.GIVE, target=self.seller))
                    self.state = UnloadInSellerStatesEnum.IN_EXCHANGE_WITH_SELLER
                    return True
                else:
                    Logger().debug("Seller not found in the bank map")
            else:
                Logger().debug("No entitiesFrame found")
            Kernel().worker.terminated.wait(2)

    def waitForSellerIdleStatus(self):
        currentMapId = PlayedCharacterManager().currentMap.mapId
        rpcFrame: BotRPCFrame = Kernel().worker.getFrame("BotRPCFrame")
        while not self.stopWaitingForSeller.is_set():
            sellerStatus = rpcFrame.askForStatusSync(self.seller.login)
            Logger().debug("Seller status: %s", sellerStatus)
            if sellerStatus == "idle":
                rpcFrame.askComeToCollect(self.seller.login, self.bankInfos, BotConfig().character)
                if currentMapId != self.bankInfos.npcMapId:
                    Kernel().worker.addFrame(BotAutoTripFrame(self.bankInfos.npcMapId))
                    self.state = UnloadInSellerStatesEnum.WALKING_TO_BANK
                else:
                    Watcher(target=self.waitForSellerToComme).start()
                    self.state = UnloadInSellerStatesEnum.WAITING_FOR_SELLER
                return True
            Kernel().worker.terminated.wait(2)

    def start(self):
        self.bankInfos = Localizer.getBankInfos()
        Logger().debug("Bank infos: %s", self.bankInfos.__dict__)
        currentMapId = PlayedCharacterManager().currentMap.mapId
        self._startMapId = currentMapId
        self._startRpZone = PlayedCharacterManager().currentZoneRp
        Watcher(target=self.waitForSellerIdleStatus).start()

    def process(self, msg: Message) -> bool:

        if isinstance(msg, AutoTripEndedMessage):
            Logger().debug("AutoTripEndedMessage received")
            if self.state == UnloadInSellerStatesEnum.RETURNING_TO_START_POINT:
                Kernel().worker.removeFrame(self)
                Kernel().worker.process(SellerCollectedGuestItemsMessage())
            elif self.state == UnloadInSellerStatesEnum.WALKING_TO_BANK:
                Watcher(target=self.waitForSellerToComme).start()
                self.state = UnloadInSellerStatesEnum.WAITING_FOR_SELLER
            return True

        elif isinstance(msg, MapComplementaryInformationsDataMessage):
            if self.state == UnloadInSellerStatesEnum.WAITING_FOR_MAP:
                self.state = UnloadInSellerStatesEnum.IDLE
                self.start()

        elif isinstance(msg, ExchangeConcludedMessage):
            if not self.return_to_start:
                Kernel().worker.removeFrame(self)
                Kernel().worker.process(SellerCollectedGuestItemsMessage())
            else:
                self.state = UnloadInSellerStatesEnum.RETURNING_TO_START_POINT
                Kernel().worker.addFrame(BotAutoTripFrame(self._startMapId, self._startRpZone))
