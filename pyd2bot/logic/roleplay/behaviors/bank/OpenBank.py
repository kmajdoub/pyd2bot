
from pyd2bot.data.enums import ServerNotificationEnum
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.misc.Localizer import BankInfos, Localizer
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.enums.ExchangeTypeEnum import \
    ExchangeTypeEnum
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class OpenBank(AbstractBehavior):
    STORAGE_OPEN_TIMED_OUT = 9874521
    WRONG_EXCHANGE_TYPE = 556988
    INSUFFICIENT_KAMAS = 3258253
    ERROR_BANK_NOT_FOUND = 32582543
    
    def __init__(self, return_to_start=None):
        super().__init__()
        self.return_to_start = return_to_start

    def _on_search_nearest_bank_storage(self, code, error, path, infos: BankInfos):
        if path is None or error:
            return self.finish(self.ERROR_BANK_NOT_FOUND, f"No accessible bank storage found, search ended with result error[{code}] {error}")
        
        self.infos = infos
        self.path_to_bank = path
        self._on_bank_infos()
        
    def run(self, bankInfos: BankInfos=None, path_to_bank=None) -> bool:
        if bankInfos is None:
            return Localizer.findClosestBankAsync(callback=self._on_search_nearest_bank_storage)
        
        self.infos = bankInfos
        self.path_to_bank = path_to_bank
        self._on_bank_infos()

    def _on_bank_infos(self):
        Logger().debug("Bank infos: %s", self.infos.__dict__)
        self._startMapId = PlayedCharacterManager().currentMap.mapId
        self._startRpZone = PlayedCharacterManager().currentZoneRp
        self.on(KernelEvent.ServerTextInfo, self.onTextInformation)
        
        self.npc_dialog(
            self.infos.npcMapId, 
            self.infos.npcId, 
            self.infos.npcActionId, 
            self.infos.questionsReplies,
            path_to_npc=self.path_to_bank,
            callback=self.onBankManDialogEnded,
        )

    def onTextInformation(self, event, msgId, msgType, textId, msgContent, params):
        if textId == ServerNotificationEnum.NOT_ENOUGH_KAMAS:
            self.finish(self.INSUFFICIENT_KAMAS, "Insufficient kamas to open bank")
        elif textId == ServerNotificationEnum.KAMAS_LOST:
            self.send(KernelEvent.KamasLostFromBankOpen, int(params[0]))
        elif textId == ServerNotificationEnum.BANK_OPEN_TAX:
            self.send(KernelEvent.KamasLostFromBankOpen, int(params[0]))

    def onBankManDialogEnded(self, code, error):
        if error:
            return self.finish(code, error)

        Logger().info("Ended bank man dialog waiting for storage to open...")
        self.once(
            event_id=KernelEvent.ExchangeBankStartedWithStorage, 
            callback=self.onStorageOpen,
            timeout=30,
            ontimeout=lambda: self.finish(self.STORAGE_OPEN_TIMED_OUT, "Dialog with Bank NPC ended correctly but storage didnt open on time!"),
        )
    
    def onBankContent(self, event, objects, kamas):
        self.finish(0)
        
    def onStorageOpen(self, event, exchangeType, pods):
        if exchangeType == ExchangeTypeEnum.BANK:
            Logger().info("Bank storage opened")
            self.once(KernelEvent.InventoryContent, self.onBankContent)
        else:
            self.finish(self.WRONG_EXCHANGE_TYPE ,f"Expected BANK storage to open but another type of exchange '{ExchangeTypeEnum.BANK}'!")
