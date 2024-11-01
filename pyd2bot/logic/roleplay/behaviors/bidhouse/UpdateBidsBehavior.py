from typing import Set

from pyd2bot.logic.roleplay.behaviors.bidhouse.AbstractMarketBehavior import AbstractMarketBehavior
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.KamasUpdateMessage import KamasUpdateMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHouseItemAddOkMessage import ExchangeBidHouseItemAddOkMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.items.InventoryWeightMessage import InventoryWeightMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.items.ObjectDeletedMessage import ObjectDeletedMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.items.ObjectQuantityMessage import ObjectQuantityMessage

class UpdateBidsBehavior(AbstractMarketBehavior):
    """Updates old listings to stay competitive while protecting against manipulation"""
    
    MIN_PRICE_RATIO = 0.5  # Minimum price vs average market price
    MIN_UPDATE_AGE_HOURS = 0.25  # Only update listings older than this
    DEFAULT_MAX_UPDATES = 10  # Default number of updates per run

    REQUIRED_SEQUENCE = {
        "KamasUpdateMessage",
        "ExchangeBidHouseItemRemoveOkMessage", 
        "ExchangeBidHouseItemAddOkMessage",
        "ExchangeBidHouseInListUpdatedMessage"
    }
    
    def __init__(self, object_gid: int, quantity: int, item_category, 
                 min_update_age_hours: float = None,
                 max_updates: int = DEFAULT_MAX_UPDATES):
        super().__init__(object_gid, quantity)
        self._received_sequence: Set[str] = set()
        self.min_update_age_hours = min_update_age_hours or self.MIN_UPDATE_AGE_HOURS
        self.item_category = item_category
        self.max_updates = max_updates
        self._updates_performed = 0

    def run(self) -> bool:
        """Start update bids process"""

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
       """Track update sequence completion"""
       if self._state != "UPDATING":
           return
           
       msg_type = msg.__class__.__name__
       
       if msg_type in self.REQUIRED_SEQUENCE:
           self._received_sequence.add(msg_type)

       # Check if sequence is complete
       if self._received_sequence >= self.REQUIRED_SEQUENCE:
           self._received_sequence.clear()
           self._updates_performed += 1
           
           if self._updates_performed >= self.max_updates:
               self._logger.info(f"Completed all {self.max_updates} updates for this run")
               self.close_marketplace()
           else:
               self._logger.info(f"Update {self._updates_performed}/{self.max_updates} complete, starting next...")
               self.send_price_check()

    def _handle_price_msg(self, msg) -> None:
        """Process next listing update with improved price strategy"""
        if self._updates_performed >= self.max_updates:
            self._logger.info(f"Update limit reached ({self.max_updates})")
            return self.close_marketplace()

        updatable = self._market.get_updatable_listings(
            self.quantity, 
            self.min_update_age_hours,
            self.MIN_PRICE_RATIO
        )
        
        if not updatable:
            self._logger.info("No more listings need updating")
            return self.close_marketplace()

        # Log progress on first update
        if self._updates_performed == 0:
            remaining = len(updatable) - self.max_updates
            self._logger.info(
                f"Updating {min(self.max_updates, len(updatable))} listings "
                f"({remaining if remaining > 0 else 'none'} will wait for next run)"
            )

        # Update highest price listing
        listing = updatable[0]
        
        # NEW PRICE STRATEGY:
        # 1. If we're not the lowest price, target slightly above current minimum
        # 2. If we are the lowest, maintain our price
        current_min = self._market.min_prices[self.quantity]
        min_acceptable = int(self._market.avg_prices[self.quantity] * self.MIN_PRICE_RATIO)
        
        our_listings = self._market.get_listings(self.quantity)
        we_have_lowest = our_listings and our_listings[0].price == current_min
        
        if we_have_lowest:
            target_price = current_min  # Keep our competitive position
        else:
            # Target slightly above current minimum to avoid price war
            target_price = max(
                min_acceptable,
                current_min + max(1, int(current_min * 0.01))  # Stay 1% above min
            )

        if self._can_afford_tax(target_price):
            self._received_sequence.clear()
            self.send_price_update(target_price, listing.uid)
        else:
            self.finish(self.ERROR_CODES["INSUFFICIENT_KAMAS"])

    def _handle_sell_mode_msg(self, msg) -> None:
        """Start update process"""
        self.send_search_request()

    def _handle_search_msg(self, msg) -> None:
        """Get current prices"""
        self.send_price_check()
        
    