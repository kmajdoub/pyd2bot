from enum import Enum

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.AutoTrip import AutoTrip
from pyd2bot.logic.roleplay.frames.BotBankInteractionFrame import \
    BotBankInteractionFrame
from pyd2bot.logic.roleplay.frames.BotExchangeFrame import (
    BotExchangeFrame, ExchangeDirectionEnum)
from pyd2bot.misc.Localizer import BankInfos
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class CollecteState(Enum):
    WATING_MAP = 0
    IDLE = 4
    GOING_TO_BANK = 1
    INSIDE_BANK = 8
    TREATING_BOT_UNLOAD = 2
    UNLOADING_IN_BANK = 3
    WAITING_FOR_BOT_TO_ARRIVE = 5
    EXCHANGING_WITH_GUEST = 6
    EXCHANGE_OPEN_REQUEST_RECEIVED = 7
    EXCHANGE_OPEN = 9
    EXCHANGE_ACCEPT_SENT = 10


class CollectItems(AbstractBehavior):

    def __init__(self):
        super().__init__()

    def start(self, bankInfos: BankInfos, guest: dict, items: list = None, callback=None) -> bool:
        if self.running.is_set():
            return self.finish(False, "[CollectFromGuest] Already running")
        self.running.set()
        self.guest = guest
        self.bankInfos = bankInfos
        self.items = items
        self.callback = callback
        self.state = CollecteState.WATING_MAP
        if PlayedCharacterManager().currentMap is not None:
            self.state = CollecteState.GOING_TO_BANK
            self.goToBank()
        else:
            Logger().info("[CollectFromGuest] Waiting for map...")
            KernelEventsManager().onceMapProcessed(self.goToBank)
        return True

    def goToBank(self):
        self.state = CollecteState.GOING_TO_BANK
        currentMapId = PlayedCharacterManager().currentMap.mapId
        if currentMapId != self.bankInfos.npcMapId:
            AutoTrip().start(self.bankInfos.npcMapId, 1, self.onTripEnded)
        else:
            self.state = CollecteState.INSIDE_BANK
            Kernel().worker.addFrame(BotExchangeFrame(ExchangeDirectionEnum.RECEIVE, self.guest, self.onExchangeConcluded, self.items))
            self.state = CollecteState.EXCHANGING_WITH_GUEST

    def onTripEnded(self, status, error):
        if error is not None:
            return self.finish(False, error)
        if self.state == CollecteState.GOING_TO_BANK:
            self.state = CollecteState.INSIDE_BANK
            Kernel().worker.addFrame(BotExchangeFrame(ExchangeDirectionEnum.RECEIVE, self.guest, self.onExchangeConcluded, self.items))
            self.state = CollecteState.EXCHANGING_WITH_GUEST
        else:
            return self.finish(False, "[CollectFromGuest] Trip ended but state is not GOING_TO_BANK")
    
    def onExchangeConcluded(self, status, error):
        if error:
            return self.finish(status, error)
        Logger().info("[CollectFromGuest] Exchange with guest ended successfully.")
        self.state = CollecteState.UNLOADING_IN_BANK
        Kernel().worker.addFrame(BotBankInteractionFrame(self.bankInfos, self.onBankInteractionEnded))
        return True
    
    def onBankInteractionEnded(self, status, error):
        if error:
            return self.finish(status, error)
        self.finish(True, None)
