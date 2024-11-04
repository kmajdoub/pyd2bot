from enum import Enum
from typing import Set, Optional

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

class UpdateBid(AbstractBehavior):
    """Handles updating a single market listing price"""
    
    REQUIRED_SEQUENCE = {
        "KamasUpdateMessage",
        "ExchangeBidHouseItemRemoveOkMessage", 
        "ExchangeBidHouseItemAddOkMessage"
    }
    
    class ERROR_CODES(Enum):
        INSUFFICIENT_KAMAS = 999999902
        PRICE_ERROR = 999999903
    
    def __init__(self, object_gid: int, quantity: int, listing_uid: int, new_price: int):
        super().__init__()
        self.object_gid = object_gid
        self.quantity = quantity
        self.listing_uid = listing_uid
        self.target_price = new_price
        self._received_sequence: Set[str] = set()
        self._logger = Logger()

    @property
    def bids_manager(self):
        return self._market_frame._bids_manager

    def run(self) -> bool:
        """Start the bid update process"""
        self._market_frame = Kernel().marketFrame
        self.on(KernelEvent.MessageReceived, self._on_server_message)
        self.open_market(
            from_gid=self.object_gid,
            callback=self._on_market_open
        )
        return True

    def _on_market_open(self, code: int, error: str) -> None:
        """Handle market opened"""
        if error:
            return self.finish(code, error)
        
        if self._market_frame._current_mode != "sell":
            self._market_frame.switch_mode("sell", self._on_sell_mode)
            return True
        else:
            Logger().info("Market already in sell mode, skipping mode switch")
            self._on_sell_mode(None, None)

    def _on_sell_mode(self, event, mode) -> None:
        """Handle sell mode activated"""
        self._logger.info("Getting current market prices")
        self._market_frame.check_price(self.object_gid, self._on_price_info)

    def _on_price_info(self, event, msg) -> None:
        """Process price update"""
        if self._can_afford_tax(self.target_price):
            self._logger.info(f"Updating listing {self.listing_uid} to price {self.target_price}")
            self._market_frame.send_update_listing(self.listing_uid, self.quantity, self.target_price)
        else:
            self.finish(self.ERROR_CODES.INSUFFICIENT_KAMAS, "Insufficient kamas for tax")

    def _on_server_message(self, event, msg) -> None:
        """Watch for update sequence completion and provide detailed logging"""
        msg_type = msg.__class__.__name__
        
        if msg_type in self.REQUIRED_SEQUENCE:
            self._received_sequence.add(msg_type)
            remaining = self.REQUIRED_SEQUENCE - self._received_sequence
            
            self._logger.debug(
                f"Received {msg_type} ({len(self._received_sequence)}/{len(self.REQUIRED_SEQUENCE)})"
                + (f", waiting for: {', '.join(remaining)}" if remaining else "")
            )
            
            # Log specific message details
            if msg_type == "KamasUpdateMessage":
                self._logger.info(f"Kamas updated: {msg.kamasTotal:,}")
            elif msg_type == "ExchangeBidHouseItemRemoveOkMessage":
                self._logger.info("Old listing removed successfully")
            elif msg_type == "ExchangeBidHouseItemAddOkMessage":
                self._logger.info("New listing added successfully")
                
        # Sequence complete
        if self._received_sequence >= self.REQUIRED_SEQUENCE:
            self._market_frame._state = "IDLE"
            self._logger.info("✓ Update sequence completed successfully")
            self.finish(0)

    def _can_afford_tax(self, price: int) -> bool:
        """Check if player can afford tax"""
        tax = self.bids_manager.calculate_tax(price)
        return PlayedCharacterManager().characteristics.kamas >= tax
