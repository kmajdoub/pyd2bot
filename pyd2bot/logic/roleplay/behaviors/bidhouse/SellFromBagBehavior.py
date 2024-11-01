from typing import Set

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

    def _handle_behavior_specific(self, msg) -> None:
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
            self._market.handle_listing_add(msg)
            
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
        self._try_sell()

    def _try_sell(self) -> None:
        """Attempt to sell at profitable price"""
        prices = self._market.get_quantity_info(self.quantity)
        if not prices["min_price"] or not prices["avg_price"]:
            return self.finish(1, "Unable to get market prices")

        min_acceptable = int(prices["avg_price"] * self.MIN_PRICE_RATIO)
        
        # Check if the lowest price is our own listing
        our_listings = self._market.get_listings(self.quantity)
        if our_listings and our_listings[0].price == prices["min_price"]:
            # If we have the lowest price, use that price instead of undercutting
            target_price = prices["min_price"]
            self._logger.debug(f"We have the lowest price already at {target_price}")
        else:
            # Otherwise undercut the current lowest price
            target_price = max(min_acceptable, prices["min_price"] - 1)

        if prices["min_price"] >= min_acceptable:
            if self._can_afford_tax(target_price):
                self.send_new_listing(target_price)
            else:
                self.finish(self.ERROR_CODES["INSUFFICIENT_KAMAS"], "Insufficient kamas for listing tax")
        else:
            self._logger.warning(f"Market price {prices['min_price']} below minimum {min_acceptable}")
            self.close_marketplace()
