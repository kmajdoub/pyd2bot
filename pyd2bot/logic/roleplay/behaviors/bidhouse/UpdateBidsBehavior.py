from typing import Set

from pyd2bot.logic.roleplay.behaviors.bidhouse.AbstractMarketBehavior import AbstractMarketBehavior

class UpdateBidsBehavior(AbstractMarketBehavior):
    """Updates old listings to stay competitive while protecting against manipulation"""
    
    MIN_PRICE_RATIO = 0.8  # Minimum price vs average market price
    MIN_UPDATE_AGE_HOURS = 3.0  # Only update listings older than this

    def __init__(self, object_gid: int, quantity: int):
        super().__init__(object_gid, quantity)
        self._received_sequence: Set[str] = set()

    def _handle_behavior_specific(self, msg) -> None:
        """Track update sequence completion"""
        if self._state != "UPDATING":
            return

        message_types = {
            "KamasUpdateMessage",
            "ExchangeBidHouseItemAddOkMessage", 
            "ExchangeBidHouseItemRemoveOkMessage",
            "InventoryWeightMessage"
        }
        
        msg_type = msg.__class__.__name__
        if msg_type in message_types:
            self._received_sequence.add(msg_type)

        # When sequence complete, look for next update
        if self._received_sequence >= message_types:
            self._received_sequence.clear()
            self.send_price_check()

    def _handle_sell_mode_msg(self, msg) -> None:
        """Start update process"""
        self.send_search_request()

    def _handle_search_msg(self, msg) -> None:
        """Get current prices"""
        self.send_price_check()
        
    def _handle_price_msg(self, msg) -> None:
        """Find and process update candidates"""
        updatable = self._market.get_updatable_listings(
            self.quantity, 
            self.MIN_UPDATE_AGE_HOURS,
            self.MIN_PRICE_RATIO
        )
        
        if not updatable:
            return self.finish(0, "No listings need updating")

        # Get target price
        new_price = self._market.get_safe_price(self.quantity, self.MIN_PRICE_RATIO)
        if not new_price:
            self._logger.warning("Market price too low for safe updates")
            return self.finish(0)

        # Update oldest listing
        listing = updatable[0]  # Already sorted oldest first
        if self._can_afford_tax(new_price):
            self.send_price_update(new_price, listing.uid)
        else:
            self.finish(self.ERROR_CODES["INSUFFICIENT_KAMAS"], "Insufficient kamas for update tax")