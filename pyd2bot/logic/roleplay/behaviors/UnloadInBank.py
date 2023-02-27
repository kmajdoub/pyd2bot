import threading
from enum import Enum
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.AutoTrip import AutoTrip
from pyd2bot.logic.roleplay.frames.BotBankInteractionFrame import \
    BotBankInteractionFrame
from pyd2bot.misc.Localizer import Localizer
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class BankUnloadStates(Enum):
    WAITING_FOR_MAP = -1
    IDLE = 0
    WALKING_TO_BANK = 1
    ISIDE_BANK = 2
    INTERACTING_WITH_BANK_MAN = 3
    RETURNING_TO_START_POINT = 4


class UnloadInBank(AbstractBehavior):


    def __init__(self):
        super().__init__()
        self.return_to_start = None
        self.callback = None

    def start(self, callback=None, return_to_start=True) -> bool:
        if self.running.is_set():
            return self.callback(False, "UnloadInBank already running")
        self.running.set()
        self.return_to_start = return_to_start
        self.callback = callback
        if PlayedCharacterManager().currentMap is None:
            self.state = BankUnloadStates.WAITING_FOR_MAP
            KernelEventsManager().onceMapProcessed(self.start)
            return
        self.infos = Localizer.getBankInfos()
        Logger().debug("Bank infos: %s", self.infos.__dict__)
        currentMapId = PlayedCharacterManager().currentMap.mapId
        self._startMapId = currentMapId
        self._startRpZone = PlayedCharacterManager().currentZoneRp
        if currentMapId != self.infos.npcMapId:
            self.state = BankUnloadStates.WALKING_TO_BANK
            AutoTrip().start(self.infos.npcMapId, 1, self.onAutoTripEnded)
        else:
            self.state = BankUnloadStates.INTERACTING_WITH_BANK_MAN
            Kernel().worker.addFrame(BotBankInteractionFrame(self.infos, self.onBankInteractionEnded))
        return True

    def onBankInteractionEnded(self, status, error):
        if error:
            return self.finish(status, error)
        if not self.return_to_start:
            self.state = BankUnloadStates.IDLE
            self.finish(True, None)
        else:
            self.state = BankUnloadStates.RETURNING_TO_START_POINT
            AutoTrip().start(self._startMapId, 1, self.onAutoTripEnded)
            
    def onAutoTripEnded(self, status, error):
        if error:
            Logger().error("[UnloadInBankFrame] Error while auto-tripping: %s", error)
            return self.finish(status, error)
        if self.state == BankUnloadStates.RETURNING_TO_START_POINT:
            Logger().error("[UnloadInBankFrame] Returned to start map.")
            self.state = BankUnloadStates.IDLE
            self.finish(True, None)
        elif self.state == BankUnloadStates.WALKING_TO_BANK:
            Logger().error("[UnloadInBankFrame] Reached the bank map.")
            self.state = BankUnloadStates.ISIDE_BANK
            Kernel().worker.addFrame(BotBankInteractionFrame(self.infos, self.onBankInteractionEnded))
            self.state = BankUnloadStates.INTERACTING_WITH_BANK_MAN