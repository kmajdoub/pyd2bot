from typing import Set

from pyd2bot.data.enums import ServerNotificationEnum
from pyd2bot.logic.roleplay.behaviors.bidhouse.AbstractMarketBehavior import AbstractMarketBehavior
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.KamasUpdateMessage import KamasUpdateMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHouseItemAddOkMessage import ExchangeBidHouseItemAddOkMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.items.ObjectDeletedMessage import ObjectDeletedMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.items.ObjectQuantityMessage import ObjectQuantityMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.items.InventoryWeightMessage import InventoryWeightMessage

class SellFromBagBehavior(AbstractMarketBehavior):
    """Sells items from inventory in batches at competitive prices"""
    
    MIN_PRICE_RATIO = 0.5 # Minimum acceptable price vs market average
    
    # Server response sequence for a sale
    REQUIRED_SEQUENCE = {
        "quantity",  # Inventory quantity update
        "kamas",    # Kamas update after tax
        "add",      # Listing confirmation
        "weight"    # Inventory weight update
    }

    def __init__(self, object_gid: int, quantity: int):
        super().__init__(object_gid, quantity)
        self._quantity_in_inventory: int = 0
        self._received_sequence: Set[str] = set()

    def run(self) -> bool:
        """Start selling process"""
        # Get item and validate quantity
        self._item = self.get_item_from_inventory(self.object_gid)
        if not self._item:
            return self.finish(self.ERROR_CODES["OBJECT_NOT_FOUND"], "Item not found in inventory")
        
        self.item_category = self._item.category
        self._quantity_in_inventory = self._item.quantity
        if self._quantity_in_inventory < self.quantity:
            return self.finish(
                self.ERROR_CODES["INVALID_QUANTITY"], 
                f"Need {self.quantity} items, only have {self._quantity_in_inventory}"
            )

        # Validate market access
        if not self._validate_marketplace_access():
            return False

        # Travel if needed, otherwise start selling
        if self.hdv_vertex != PlayedCharacterManager().currVertex:
            self.travelUsingZaap(
                self.hdv_vertex.mapId, 
                self.hdv_vertex.zoneId,
                callback=self._on_marketplace_map_reached
            )
        else:
            self._on_marketplace_map_reached(None, None)
            
        return True

    def _on_server_notif(self, event, msgId, msgType, textId, msgContent, params):
        if textId == ServerNotificationEnum.CANT_SELL_ANYMORE_ITEMS:
            self.finish(self.ERROR_CODES["NO_MORE_SELL_SLOTS"], "There is no more sell slots")
            
    def _process_message(self, msg) -> None:
        """Track complete server response sequence"""
        if self._state != "SELLING":
            return

        # Track sequence messages
        if isinstance(msg, (ObjectQuantityMessage, ObjectDeletedMessage)):
            self._received_sequence.add("quantity")
            if isinstance(msg, ObjectDeletedMessage):
                self._quantity_in_inventory = 0
            else:
                self._quantity_in_inventory = msg.quantity

        elif isinstance(msg, KamasUpdateMessage):
            self._received_sequence.add("kamas")
            
        elif isinstance(msg, ExchangeBidHouseItemAddOkMessage):
            self._received_sequence.add("add")
            
        elif isinstance(msg, InventoryWeightMessage):
            self._received_sequence.add("weight")

        # Check if sequence is complete
        if self._received_sequence >= self.REQUIRED_SEQUENCE:
            self._received_sequence.clear()

            if self._quantity_in_inventory >= self.quantity:
                self.send_price_check()
            else:
                self._logger.info("Selling complete - no more full batches available")
                self.close_marketplace()

    def _handle_sell_mode_msg(self, msg) -> None:
        """Market opened - start price checks"""
        self.send_search_request()

    def _handle_search_msg(self, msg) -> None:
        """Search complete - check prices"""
        self.send_price_check()
        
    def _handle_price_msg(self, msg) -> None:
        """Got prices - attempt sale if profitable"""
        target_price, error = self._market.get_sell_price(
            self.object_gid, 
            self.quantity,
            self.MIN_PRICE_RATIO
        )
        
        if error:
            self._logger.warning(error)
            return self.close_marketplace()
            
        if self._can_afford_tax(target_price):
            self.send_new_listing(target_price)
        else:
            self.close_marketplace(self.ERROR_CODES["INSUFFICIENT_KAMAS"], "Insufficient kamas for listing tax")
