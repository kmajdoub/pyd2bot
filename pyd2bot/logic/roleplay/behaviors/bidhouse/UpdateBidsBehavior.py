from typing import Set

from pyd2bot.logic.roleplay.behaviors.bidhouse.AbstractMarketBehavior import AbstractMarketBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.datacenter.items.Item import Item
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager


class UpdateBidsBehavior(AbstractMarketBehavior):
    """Updates old listings to stay competitive while protecting against manipulation"""
    
    MIN_PRICE_RATIO = 0.5  # Minimum price vs average market price
    MIN_UPDATE_AGE_HOURS = 0.25  # Only update listings older than this
    DEFAULT_MAX_UPDATES = 5  # Default number of updates per run

    REQUIRED_SEQUENCE = {
        "KamasUpdateMessage",
        "ExchangeBidHouseItemRemoveOkMessage", 
        "ExchangeBidHouseItemAddOkMessage",
        "ExchangeBidHouseInListUpdatedMessage"
    }
    
    def __init__(self, object_gid: int, quantity: int, 
                 min_update_age_hours: float = None,
                 max_updates: int = DEFAULT_MAX_UPDATES):
        super().__init__(object_gid, quantity)
        self._received_sequence: Set[str] = set()
        self.min_update_age_hours = min_update_age_hours or self.MIN_UPDATE_AGE_HOURS
        self.max_updates = max_updates
        self._updates_performed = 0

    def run(self) -> bool:
        """Start update bids process"""
        self.on(KernelEvent.AssetPriceChanged, self._handle_price_change)
        self.on(KernelEvent.NewMarketLow, self._handle_new_market_low)
    
        self._item = Item.getItemById(self.object_gid, False)
        if not self._item:
            return self.finish(self.ERROR_CODES["OBJECT_NOT_FOUND"], "Item not found in inventory")
        
        self.item_category = self._item.category
        
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

    def _handle_price_change(self, event, gid, quantity, old_price, new_price):
        # React to any price change
        pass

    def _handle_new_market_low(self, event, gid, quantity, old_price, new_price):
        # React specifically to prices dropping below our listings
        pass

    def _process_message(self, msg) -> None:
        """Track update sequence completion"""
        if self._state != "UPDATING":
            return
            
        msg_type = msg.__class__.__name__
        
        if msg_type in self.REQUIRED_SEQUENCE:
            self._received_sequence.add(msg_type)

        # Check if sequence is complete
        if self._received_sequence >= self.REQUIRED_SEQUENCE:
            self._state = "IDLE"
            self._received_sequence.clear()
            self._on_update_ended()

    def _on_update_ended(self):
        self._updates_performed += 1
           
        if self._updates_performed >= self.max_updates:
            self._logger.info(f"Completed all {self.max_updates} updates for this run")
            self._on_idle()
        else:
            self._logger.info(f"Update {self._updates_performed}/{self.max_updates} complete, starting next...")
            self.send_price_check()
    
    def _on_idle(self):
        """Handle completion of update cycle"""
        self.close_marketplace()
                       
    def _handle_price_msg(self, msg) -> None:
        """Process next listing update"""
        if self._updates_performed >= self.max_updates:
            self._logger.info(f"Update limit reached ({self.max_updates})")
            return self.close_marketplace()

        updatable, target_price, error = self._market.get_updatable_listings(
            self.object_gid,
            self.quantity, 
            self.min_update_age_hours,
            self.MIN_PRICE_RATIO
        )
        
        if error:
            self._logger.warning(f"Cannot update price: {error}")
            return self.close_marketplace(1, f"Cannot update price: {error}")
        
        if not updatable:
            self._logger.info("No more listings need updating")
            self._on_idle()
            return

        if self._updates_performed == 0:
            remaining = len(updatable) - self.max_updates
            self._logger.info(
                f"Updating {min(self.max_updates, len(updatable))} listings "
                f"({remaining if remaining > 0 else 'none'} will wait for next run)"
            )

        listing = updatable[0]
        if self._can_afford_tax(target_price):
            self._received_sequence.clear()
            self._logger.info(f"Updating listing uid={listing.uid} price={listing.price}->{target_price}")
            self.send_price_update(target_price, listing.uid)
        else:
            self.close_marketplace(self.ERROR_CODES["INSUFFICIENT_KAMAS"], "Insufficient kamas to pay tax")

    def _handle_sell_mode_msg(self, msg) -> None:
        """Start monitoring with initial price check"""
        self._logger.info("Market opened - starting price monitoring")
        self.send_search_request()

    def _handle_search_msg(self, msg) -> None:
        """Get current prices"""
        self.send_price_check()
        
    