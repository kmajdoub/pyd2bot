from pyd2bot.data.enums import ServerNotificationEnum
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InactivityManager import InactivityManager
from pydofus2.com.ankamagames.dofus.network.messages.common.basic.BasicPingMessage import BasicPingMessage

from pyd2bot.logic.roleplay.behaviors.bidhouse.UpdateMarketBids import UpdateMarketBids
import threading

from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer

class MonitorMarket(UpdateMarketBids):
    """Market monitor that maintains target number of listings at market price through reactive updates"""
    
    DEFAULT_MAX_TOP_BIDS = 3  # Maximum number of listings to maintain at/below market price
    DEFAULT_MAX_UPDATES = 10
    
    def __init__(self, 
                 object_gid: int, 
                 quantity: int,
                 min_update_age_hours: float = UpdateMarketBids.MIN_UPDATE_AGE_HOURS,
                 max_top_bids: int = DEFAULT_MAX_TOP_BIDS):
        super().__init__(object_gid, quantity, min_update_age_hours)
        self.max_top_bids = max_top_bids
        self._busy = threading.Event()
        
    def run(self) -> bool:
        """Start monitoring with initial price check and reactive updates"""
        self.on(KernelEvent.NewMarketLow, self._handle_new_market_low)
        self.on(KernelEvent.ServerTextInfo, self._on_server_notif)
        return super().run()

    def _on_server_notif(self, event, msgId, msgType, textId, text, params):
        """Handle server notifications like inactivity warnings"""
        if textId == ServerNotificationEnum.INACTIVITY_WARNING:
            pingMsg = BasicPingMessage()
            pingMsg.init(True)
            ConnectionsHandler().send(pingMsg) # Fake activity to not get disconnected
            
    def _handle_new_market_low(self, event, gid: int, quantity: int, old_price: int, new_price: int):
        """React to new market lows with immediate reactive update"""
        if gid != self.object_gid or quantity != self.quantity or self._busy.is_set() or self._state == "UPDATING":
            return
        
        self._logger.info(f"New market low detected ({old_price}->{new_price}), triggering reactive update after 60 seconds")
        self._busy.set()
        BenchmarkTimer(60, self.send_price_check).start()
            
    def _handle_price_msg(self, msg) -> None:
        """Handle price updates only when we're below target market presence"""
        current_market_price = self._market_listings.min_price[self.object_gid][self.quantity]
        current_at_market = self._market_listings.count_listings_le_market(self.object_gid, self.quantity)
        InactivityManager().activity()
        
        if current_at_market >= self.max_top_bids:
            self._logger.info(
                f"Already have {current_at_market}/{self.max_top_bids} listings at/below market price ({current_market_price})"
            )
            return self._on_idle()

        # Get updatable listings without minimum age requirement
        updatable, target_price, error = self._market_listings.get_updatable_listings(
            self.object_gid,
            self.quantity,
            0,  # No age threshold for reactive updates
            self.MIN_PRICE_RATIO
        )
        
        if error:
            self._logger.warning(f"Cannot update price: {error}")
            return self._on_idle()
        
        if not updatable:
            self._logger.info("No listings available for update")
            return self._on_idle()

        # Calculate how many listings we need to update
        needed_updates = min(
            self.max_top_bids - current_at_market, 
            len(updatable)
        )
        
        if needed_updates <= 0:
            self._logger.info("No updates needed")
            return self._on_idle()

        self._logger.info(
            f"Updating {needed_updates} listings to reach target of {self.max_top_bids} "
            f"at/below market price ({current_market_price})"
        )

        listing = updatable[0]  # Get highest price listing to update
        if self._can_afford_tax(target_price):
            self._received_sequence.clear()
            self._logger.info(
                f"Updating listing uid={listing.uid} "
                f"price={listing.price}->{target_price} "
                f"({current_at_market + 1}/{self.max_top_bids} at market)"
            )
            self.send_price_update(target_price, listing.uid)
        else:
            self.close_marketplace(
                self.ERROR_CODES["INSUFFICIENT_KAMAS"], 
                "Insufficient kamas to pay tax"
            )

    def _on_update_ended(self):
        """Handle completion of a price update"""        
        self.send_price_check()
            
    def _on_idle(self):
        """Clear reactive event and wait for next market change"""
        self._logger.info("Update cycle complete, waiting for market changes")
        self._state = "IDLE"
        self._busy.clear()
