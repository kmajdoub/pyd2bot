import threading
from enum import Enum
from typing import TYPE_CHECKING

from pyd2bot.logic.common.frames.BotRPCFrame import BotRPCFrame
from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.AutoTrip import AutoTrip
from pyd2bot.logic.roleplay.frames.BotExchangeFrame import (
    BotExchangeFrame, ExchangeDirectionEnum)
from pyd2bot.misc.Localizer import Localizer
from pyd2bot.misc.Watcher import Watcher
from pyd2bot.thriftServer.pyd2botService.ttypes import Character
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayEntitiesFrame import \
        RoleplayEntitiesFrame


class GiveItelsStates(Enum):
    WAITING_FOR_MAP = -1
    IDLE = 0
    WALKING_TO_BANK = 1
    ISIDE_BANK = 2
    RETURNING_TO_START_POINT = 4
    WAITING_FOR_SELLER = 5
    IN_EXCHANGE_WITH_SELLER = 6


class GiveItems(AbstractBehavior):

    def __init__(self):
        super().__init__()

    def start(self, sellerInfos: Character, callback, return_to_start=True) -> bool:
        if self.running.is_set():
            callback(False, "Already running")
            return
        self.running.set()
        self.seller = sellerInfos
        self.return_to_start = return_to_start
        self.callback = callback
        self.state = GiveItelsStates.IDLE
        self._start()
        return True

    @property
    def entitiesFrame(self) -> "RoleplayEntitiesFrame":
        return Kernel().worker.getFrameByName("RoleplayEntitiesFrame")

    def waitForGuestToComme(self):
        if self.entitiesFrame:
            if self.entitiesFrame.getEntityInfos(self.seller.id):
                Kernel().worker.addFrame(BotExchangeFrame(ExchangeDirectionEnum.GIVE, target=self.seller, callback=self.onExchangeConcluded))
                self.state = GiveItelsStates.IN_EXCHANGE_WITH_SELLER
                return True
            else:
                KernelEventsManager().onceActorShowed(self.seller.id, self.waitForGuestToComme)
        else:
            KernelEventsManager().onceFramePushed("RoleplayEntitiesFrame", self.waitForGuestToComme)
        Kernel().worker.terminated.wait(2)

    def waitForGuestIdleStatus(self):
        currentMapId = PlayedCharacterManager().currentMap.mapId
        rpcFrame: BotRPCFrame = Kernel().worker.getFrameByName("BotRPCFrame")
        while self.running.is_set():
            sellerStatus = rpcFrame.askForStatusSync(self.seller.login)
            Logger().info(f"[UnloadInSellerFrame] Seller status: {sellerStatus}.")
            if sellerStatus == "idle":
                rpcFrame.askComeToCollect(self.seller.login, self.bankInfos, BotConfig().character)
                if currentMapId != self.bankInfos.npcMapId:
                    self.state = GiveItelsStates.WALKING_TO_BANK
                    AutoTrip().start(self.bankInfos.npcMapId, 1, self.onTripEnded)
                else:
                    self.waitForGuestToComme()
                    self.state = GiveItelsStates.WAITING_FOR_SELLER
                return True
            Kernel().worker.terminated.wait(2)

    def _start(self):
        if PlayedCharacterManager().currentMap is None:
            return KernelEventsManager().onceMapProcessed(self._start)
        self._startMapId = PlayedCharacterManager().currentMap.mapId
        self._startRpZone = PlayedCharacterManager().currentZoneRp
        self.bankInfos = Localizer.getBankInfos()
        Watcher(self.waitForGuestIdleStatus).start()

    def onTripEnded(self, status, error):
        if error:
            return self.finish(status, error)
        if self.state == GiveItelsStates.RETURNING_TO_START_POINT:
            Logger().info("[UnloadInSellerFrame] Trip ended, returned to start point")
            return self.finish(True, None)
        elif self.state == GiveItelsStates.WALKING_TO_BANK:
            Logger().info("[UnloadInSellerFrame] Trip ended, waiting for seller to come")
            self.state = GiveItelsStates.WAITING_FOR_SELLER
            self.waitForGuestToComme()

    def onExchangeConcluded(self, status, error) -> bool:
        if error:
            return self.finish(status, error)
        if not self.return_to_start:
            return self.finish(True, None)
        else:
            self.state = GiveItelsStates.RETURNING_TO_START_POINT
            AutoTrip().start(self._startMapId, self._startRpZone, self.onTripEnded)