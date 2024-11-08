from enum import Enum
from typing import Set, Optional

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.common.managers.MarketBid import MarketBid
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

class EditBidPrice(AbstractBehavior):
    """Handles updating a single market listing price"""
    
    REQUIRED_SEQUENCE = {
        "KamasUpdateMessage",
        "ExchangeBidHouseItemRemoveOkMessage", 
        "ExchangeBidHouseItemAddOkMessage"
    }
    
    class ERROR_CODES(Enum):
        INSUFFICIENT_KAMAS = 999999902
        PRICE_ERROR = 999999903
    
    def __init__(self, bid: MarketBid, new_price: int):
        super().__init__()
        self.bid = bid
        self.new_price = new_price
        self._received_sequence: Set[str] = set()
        self._logger = Logger()

    @property
    def bids_manager(self):
        return self._market_frame._bids_manager

    def run(self) -> bool:
        """Start the bid update process"""
        self._market_frame = Kernel().marketFrame
        if self._market_frame._market_type_open is None:
            return self.finish(1, "Market is not open")
        if self._market_frame._current_mode != "sell":
            return self.finish(1, "Market is not is sell mode")
        self.on(KernelEvent.MessageReceived, self._on_server_message)
        if self._can_afford_tax(self.new_price):
            self._logger.info(f"Updating listing {self.bid.uid} to price {self.new_price}")
            self._market_frame.send_update_listing(self.bid.uid, self.bid.quantity, self.new_price)
        else:
            self.finish(self.ERROR_CODES.INSUFFICIENT_KAMAS, "Insufficient kamas for tax")

    def _on_server_message(self, event, msg) -> None:
        """Watch for update sequence completion and provide detailed logging"""
        msg_type = msg.__class__.__name__
        
        if msg_type in self.REQUIRED_SEQUENCE:
            self._received_sequence.add(msg_type)
            # remaining = self.REQUIRED_SEQUENCE - self._received_sequence
            # self._logger.debug(
            #     f"Received {msg_type} ({len(self._received_sequence)}/{len(self.REQUIRED_SEQUENCE)})"
            #     + (f", waiting for: {', '.join(remaining)}" if remaining else "")
            # )
            
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
