from typing import Set

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.KamasUpdateMessage import KamasUpdateMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHouseItemAddOkMessage import ExchangeBidHouseItemAddOkMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.items.ObjectDeletedMessage import ObjectDeletedMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.items.ObjectQuantityMessage import ObjectQuantityMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.items.InventoryWeightMessage import InventoryWeightMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.storage.StorageKamasUpdateMessage import StorageKamasUpdateMessage

class RetrieveKamasFromBank(AbstractBehavior):
    """Handles the async logic for selling a single item in the marketplace"""
    REQUIRED_SEQUENCE = {
        "kamas_bank",
        "kamas_inventory",
    }

    def __init__(self):
        super().__init__()
        self._received_sequence: Set[str] = set()
        
    def run(self) -> bool:
        """Start the sell operation"""
        if PlayedCharacterManager().characteristics.kamas <= 0:
            return self.finish(0)
        self.once(KernelEvent.MessageReceived, self._process_message)
        Kernel().exchangeManagementFrame.exchangeObjectMoveKama(PlayedCharacterManager().characteristics.kamas)

    def _process_message(self, event, msg) -> None:
        """Track complete server response sequence"""
        if isinstance(msg, KamasUpdateMessage):
            self._received_sequence.add("kamas_inventory")

        elif isinstance(msg, StorageKamasUpdateMessage):
            self._received_sequence.add("kamas_bank")

        # Check if sequence is complete
        if self._received_sequence >= self.REQUIRED_SEQUENCE:
            self._received_sequence.clear()
            self.finish(0)
