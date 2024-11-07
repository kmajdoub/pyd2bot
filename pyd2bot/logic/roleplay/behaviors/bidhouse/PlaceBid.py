from typing import Set

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.KamasUpdateMessage import KamasUpdateMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHouseItemAddOkMessage import ExchangeBidHouseItemAddOkMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.items.ObjectDeletedMessage import ObjectDeletedMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.items.ObjectQuantityMessage import ObjectQuantityMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.items.InventoryWeightMessage import InventoryWeightMessage
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

class PlaceBid(AbstractBehavior):
    """Handles the async logic for selling a single item in the marketplace"""
    
    class ERROR_CODES:
        INVALID_PRICE = 77777782

    # Server response sequence for a sale
    REQUIRED_SEQUENCE = {
        "quantity",  # Inventory quantity update
        "kamas",    # Kamas update after tax
        "add",      # Listing confirmation
        "weight"    # Inventory weight update
    }

    def __init__(self, object_uid: int, quantity: int, price: int):
        super().__init__()
        self.object_uid = object_uid
        self.price = price
        self.quantity = quantity
        self._received_sequence: Set[str] = set()
        
    def run(self) -> bool:
        """Start the sell operation"""
        if self.price <= 0:
            return self.finish(self.ERROR_CODES.INVALID_PRICE, "Invalid price")
        self.on(KernelEvent.MessageReceived, lambda _, m: self._process_message(m))
        Kernel().marketFrame.create_listing(self.object_uid, self.quantity, self.price)

    def _process_message(self, msg) -> None:
        """Track complete server response sequence"""
        if isinstance(msg, (ObjectQuantityMessage, ObjectDeletedMessage)):
            self._received_sequence.add("quantity")

        elif isinstance(msg, KamasUpdateMessage):
            self._received_sequence.add("kamas")
            
        elif isinstance(msg, ExchangeBidHouseItemAddOkMessage):
            self._received_sequence.add("add")
            
        elif isinstance(msg, InventoryWeightMessage):
            self._received_sequence.add("weight")

        # Check if sequence is complete
        if self._received_sequence >= self.REQUIRED_SEQUENCE:
            Kernel().marketFrame._state = "IDLE"
            Logger().info("Bid placed successfully")
            self.finish(0)