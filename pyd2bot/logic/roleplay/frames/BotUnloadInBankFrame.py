from pyd2bot.apis.MoveAPI import MoveAPI
from pyd2bot.logic.roleplay.frames.BotBankInteractionFrame import BotBankInteractionFrame
from pyd2bot.logic.roleplay.messages.BankInteractionEndedMessage import BankInteractionEndedMessage
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEvent, KernelEventsManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapComplementaryInformationsDataMessage import (
    MapComplementaryInformationsDataMessage,
)
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority
from pyd2bot.misc.Localizer import Localizer
from enum import Enum


class BankUnloadStates(Enum):
    WAITING_FOR_MAP = -1
    IDLE = 0
    WALKING_TO_BANK = 1
    ISIDE_BANK = 2
    INTERACTING_WITH_BANK_MAN = 3
    RETURNING_TO_START_POINT = 4


class BotUnloadInBankFrame(Frame):
    PHENIX_MAPID = None

    def __init__(self, return_to_start=True):
        super().__init__()
        self.return_to_start = return_to_start

    def pushed(self) -> bool:
        self.state = BankUnloadStates.IDLE
        if PlayedCharacterManager().currentMap is not None:
            self.start()
        else:
            self.state = BankUnloadStates.WAITING_FOR_MAP
        return True

    def pulled(self) -> bool:
        KernelEventsManager.onceFramePulled("BotUnloadInBankFrame", self.onpulled)
        return True

    def onpulled(self):
        KernelEventsManager().send(KernelEvent.INVENTORY_UNLOADED)
            
    @property
    def priority(self) -> int:
        return Priority.VERY_LOW

    def start(self):
        self.infos = Localizer.getBankInfos()
        Logger().debug("Bank infos: %s", self.infos.__dict__)
        currentMapId = PlayedCharacterManager().currentMap.mapId
        self._startMapId = currentMapId
        self._startRpZone = PlayedCharacterManager().currentZoneRp
        self._startedInBankMap = False
        if currentMapId != self.infos.npcMapId:
            self.state = BankUnloadStates.WALKING_TO_BANK
            MoveAPI.moveToMap(self.infos.npcMapId, self.onAutoTripEnded)
        else:
            self._startedInBankMap = True
            self.state = BankUnloadStates.INTERACTING_WITH_BANK_MAN
            Kernel().worker.addFrame(BotBankInteractionFrame(self.infos))

    def process(self, msg: Message) -> bool:
        
        if isinstance(msg, MapComplementaryInformationsDataMessage):
            if self.state == BankUnloadStates.WAITING_FOR_MAP:
                self.state = BankUnloadStates.IDLE
                self.start()

        elif isinstance(msg, BankInteractionEndedMessage):
            if not self.return_to_start:
                self.state = BankUnloadStates.IDLE
                Kernel().worker.removeFrame(self)
            else:
                self.state = BankUnloadStates.RETURNING_TO_START_POINT
                MoveAPI.moveToMap(self._startMapId, self.onAutoTripEnded)

    def onAutoTripEnded(self):
        if self.state == BankUnloadStates.RETURNING_TO_START_POINT:
            Logger().info("[UnloadInBankFrame] Returned to start map.")
            self.state = BankUnloadStates.IDLE
            Kernel().worker.removeFrame(self)
        elif self.state == BankUnloadStates.WALKING_TO_BANK:
            Logger().info("[UnloadInBankFrame] Reached the bank map.")
            self.state = BankUnloadStates.ISIDE_BANK
            Kernel().worker.addFrame(BotBankInteractionFrame(self.infos))
            self.state = BankUnloadStates.INTERACTING_WITH_BANK_MAN