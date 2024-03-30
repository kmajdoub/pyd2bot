
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.misc.Localizer import Localizer
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.enums.ExchangeTypeEnum import \
    ExchangeTypeEnum
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class OpenBank(AbstractBehavior):
    STORAGE_OPEN_TIMEDOUT = 9874521
    WRONG_EXCHANGE_TYPE = 556988
    NOT_ENOUGH_KAMS = 3258253
    
    def __init__(self):
        super().__init__()
        self.return_to_start = None
        self.callback = None
    
    def run(self, bankInfos=None) -> bool:
        if bankInfos is None:
            self.infos = Localizer.getBankInfos()
        else:
            self.infos = bankInfos
        Logger().debug("Bank infos: %s", self.infos.__dict__)
        self._startMapId = PlayedCharacterManager().currentMap.mapId
        self._startRpZone = PlayedCharacterManager().currentZoneRp
        self.on(KernelEvent.ServerTextInfo, self.onTextInformation)
        self.npcDialog(
            self.infos.npcMapId, 
            self.infos.npcId, 
            self.infos.npcActionId, 
            self.infos.questionsReplies, 
            callback=self.onBankManDialogEnded,
        )

    def onTextInformation(self, event, msgId, msgType, textId, msgContent, params):
        if textId == 325825:
            self.finish(self.NOT_ENOUGH_KAMS, "Not enough kamas to open bank")
            
    def onBankManDialogEnded(self, code, error):
        if error:
            return self.finish(code, error)
        Logger().info("Ended bank man dialog waiting for storage to open...")
        KernelEventsManager().once(
            event_id=KernelEvent.ExchangeBankStartedWithStorage, 
            callback=self.onStorageOpen,
            timeout=30,
            ontimeout=lambda: self.finish(self.STORAGE_OPEN_TIMEDOUT, "Dialog with Bank NPC ended correctly but storage didnt open on time!"),
            originator=self
        )
        
    def onStorageOpen(self, event, exchangeType, pods):
        if exchangeType == ExchangeTypeEnum.BANK:
            Logger().info("Bank storage opened")
            return self.finish(True, None)
        else:
            self.finish(self.WRONG_EXCHANGE_TYPE ,f"Expected BANK storage to open but another type of exchange '{ExchangeTypeEnum.BANK}'!")
