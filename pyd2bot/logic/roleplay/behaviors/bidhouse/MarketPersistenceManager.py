from typing import TYPE_CHECKING, Dict, List
from datetime import datetime, timezone
import time
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.bidhouse.MarketPersistence import MarketPersistence
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.datacenter.world.SubArea import SubArea
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.common.managers.MarketBid import MarketBid
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import PlayerManager
from pydofus2.com.ankamagames.dofus.network.types.game.data.items.ObjectItemQuantityPriceDateEffects import ObjectItemQuantityPriceDateEffects
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

if TYPE_CHECKING:
    from pyd2bot.Pyd2Bot import Pyd2Bot

class MarketPersistenceManager(AbstractBehavior):
    """Handles persistence of market operations by subscribing to market events"""
    IS_BACKGROUND_TASK = True
    
    def __init__(self, client: "Pyd2Bot"):
        super().__init__()
        self.logger = Logger()
        self.persister:MarketPersistence = None
        self.client = client
    
    @property
    def market_frame(self):
        return Kernel().marketFrame

    def run(self):
        """Register handlers for market events"""
        self.persister = MarketPersistence()
        
        self.on_multiple([
            # Market configuration updates
            (KernelEvent.MarketModeSwitch, self._on_market_init, {}),
            # Bid operations
            (KernelEvent.MarketListingAdded, self._on_listing_added, {}),
            (KernelEvent.MarketListingRemoved, self._on_listing_removed, {}),
            # Price tracking
            (KernelEvent.KamasSpentOnSellTax, self._on_tax_info, {}),
            # Sales handling
            (KernelEvent.MarketOfflineSales, self._on_offline_sales, {}),
            (KernelEvent.ItemSold, self._on_live_sale, {})
        ])
        
        return True

    def _on_live_sale(self, event, object_gid: int, quantity: int, price: int):
        """Handle live sale notification"""
        try:
            # For live sales, we'll use current time as sold_at
            self.persister.mark_bid_as_sold(
                server_id=PlayerManager().server.id,
                object_gid=object_gid,
                batch_size=quantity,
                price=price,
                sold_at=int(time.time())  # Current time in seconds
            )
        except Exception as e:
            self.logger.error(f"Failed to process live sale: {e}")
            raise
            
    def _on_market_init(self, event, mode: str):
        """Handle market initialization with rules"""
        if mode != "sell":
            return
        
        dst_sub_area = SubArea.getSubAreaByMapId(self.market_frame._market_mapId)
        
        # Save market configuration
        mgr = self.market_frame._bids_manager
        self.persister.add_or_update_market(
            market_type=self.market_frame._market_type_open,
            level_max=mgr.max_item_level,
            map_id=self.market_frame._market_mapId,
            tax_percentage=mgr.tax_percentage,
            max_sell_slots=mgr.max_item_count,
            accepted_resources=mgr.allowed_types,
            npc_id=mgr.npc_id,
            require_subscription=not dst_sub_area.basicAccountAllowed,
            gfx_id=self.market_frame._market_gfx
        )
        
        bids_data = [{
            'uid': bid.uid,
            'price': bid.price,
            'item_gid': bid.item_gid,
            'quantity': bid.quantity
        } for bid in mgr.get_all_bids()]

        self.persister.add_bids_bulk(
            bids=bids_data,
            server_id=PlayerManager().server.id,
            account_id=PlayerManager().accountId,
            session_uuid=self.client.session_run_id
        )
        
    def _on_listing_added(self, event, bid: MarketBid):
        """Handle new listing creation"""
        try:
            self.persister.add_bid(
                uid=bid.uid,
                server_id=PlayerManager().server.id,
                account_id=PlayerManager().accountId,
                session_uuid=self.client.session_run_id,
                price=bid.price,
                object_gid=bid.item_gid,
                batch_size=bid.quantity
            )
        except Exception as e:
            self.logger.error(f"Failed to persist new listing: {e}")
            raise
    
    def _on_listing_removed(self, event, bid: MarketBid):
        """Handle listing removal"""
        try:
            self.persister.delete_bid(bid.uid, PlayerManager().server.id)
        except Exception as e:
            self.logger.error(f"Failed to remove listing from persistence: {e}")
            raise
    
    def _on_tax_info(self, event, item_gid: int, quantity: int, amount_payed: int):
        """Handle tax payment tracking"""
        try:
            self.persister.record_tax_payment(
                object_gid=item_gid,
                batch_size=quantity,
                tax_amount=amount_payed,
                server_id=PlayerManager().server.id,
                account_id=PlayerManager().accountId,
                session_uuid=self.client.session_run_id
            )
        except Exception as e:
            self.logger.error(f"Failed to record tax payment: {e}")
            raise
    
    def _on_offline_sales(self, event, sales_data: list["ObjectItemQuantityPriceDateEffects"]):
        """Handle offline sales processing"""
        try:            
            for item in sales_data:
                self.persister.mark_bid_as_sold(
                    server_id=PlayerManager().server.id,
                    object_gid=item.objectGID,
                    batch_size=item.quantity,
                    price=item.price,
                    sold_at=item.date
                )
        except Exception as e:
            self.logger.error(f"Failed to process offline sales: {e}")
            raise
