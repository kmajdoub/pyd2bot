import time
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.misc.Localizer import Localizer
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import \
    ItemWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import \
    InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.npc.NpcGenericActionRequestMessage import NpcGenericActionRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.KamasUpdateMessage import KamasUpdateMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHouseInListUpdatedMessage import ExchangeBidHouseInListUpdatedMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHouseItemAddOkMessage import ExchangeBidHouseItemAddOkMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHouseItemRemoveOkMessage import ExchangeBidHouseItemRemoveOkMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHousePriceMessage import ExchangeBidHousePriceMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHouseSearchMessage import ExchangeBidHouseSearchMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidPriceForSellerMessage import ExchangeBidPriceForSellerMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeObjectModifyPricedMessage import ExchangeObjectModifyPricedMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeObjectMovePricedMessage import ExchangeObjectMovePricedMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeStartedBidBuyerMessage import ExchangeStartedBidBuyerMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeStartedBidSellerMessage import ExchangeStartedBidSellerMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeTypesItemsExchangerDescriptionForUserMessage import ExchangeTypesItemsExchangerDescriptionForUserMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.items.InventoryWeightMessage import InventoryWeightMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.items.ObjectDeletedMessage import ObjectDeletedMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.items.ObjectQuantityMessage import ObjectQuantityMessage
from pydofus2.com.ankamagames.dofus.types.enums.ItemCategoryEnum import ItemCategoryEnum
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import \
    Edge
    
class SellItem(AbstractBehavior):
    """
    Behavior for selling items in the marketplace (HDV - Hotel de Vente).
    
    Server Interaction Sequences:
    
    1. Initial Market Setup:
       - Travel to market map -> Wait for callback
       - Open market interface -> Wait for callback
       - Switch to sell mode -> Wait for ExchangeStartedBidSellerMessage
    
    2. Item Search Sequence:
       Send: ExchangeBidHouseSearchMessage
       Wait for: ExchangeTypesItemsExchangerDescriptionForUserMessage
       
    3. Price Check Sequence:
       Send: ExchangeBidHousePriceMessage
       Wait for: ExchangeBidPriceForSellerMessage
       
    4. Put Item For Sale Sequence:
       Send: ExchangeObjectMovePricedMessage
       Wait for complete sequence:
       1. ObjectQuantityMessage (inventory update)
       2. KamasUpdateMessage (tax deducted)
       3. ExchangeBidHouseItemAddOkMessage
       4. ExchangeBidHouseInListUpdatedMessage
       5. InventoryWeightMessage
       
    5. Update Existing Bid Sequence:
       Send: ExchangeObjectModifyPricedMessage
       Wait for complete sequence:
       1. KamasUpdateMessage
       2. ExchangeBidHouseInListUpdatedMessage  
       3. ExchangeBidHouseItemRemoveOkMessage
       4. ExchangeBidHouseItemAddOkMessage
       5. ExchangeBidHouseInListUpdatedMessage
    """

    SELL_MODE_ACTION_ID = 5
    MAX_UNSOLD_TIME = 12 * 3600
    MIN_PRICE_THRESHOLD = 0.6
    VALID_QUANTITIES = [1, 10, 100]
    RESOURCE_MARKETPLACE_ELEMENT_TYPE_ID = 313
    RESOURCES_MARKETPLACE_GFX_ID = 226
    ITEM_TYPE_TO_MARKETPLACE_GFX_ID_MAP = {
        ItemCategoryEnum.RESOURCES_CATEGORY: RESOURCES_MARKETPLACE_GFX_ID,
    }
    
    # errors codes 
    INVALID_QUANTITY_ERROR = 7676967
    OBJECT_NOT_FOUND_ERROR = 7676966
    CANT_LOCATE_HDV_ERROR =  7676999
    NOT_ENOUGH_KAMAS_TO_PAY_TAX = 7676968
    

    def __init__(self):
        super().__init__()
        self._prices_infos = {}
        self._sell_item_bid_infos = None
        self._sellerDescriptor = None
        self._sellBids = None
        self._item_to_sell = None
        self._state = "INIT"
        self._tax_percentage = 0
        self._current_min_price = None  # Cache current minimum price
        self._current_avg_price = None  # Cache current average price
        self._last_price_check = 0  # Track when we last checked prices      
        self._total_batches_to_sell = 0  # Track total number of batches to sell
        self._batches_sold = 0  # Track how many batches we've sold
        self._pending_quantity = 0  # Track remaining quantity to sell
        self._session_bids = set()  # Track bids made in this session by UID

        # Response sequence tracking
        self._selling_sequence_received = set()
        self._updating_sequence_received = set()
        self._pending_updates = []  # Store bids that need updating
        self._current_update = None  # Currently processing bid update
        self._logger = Logger()
        self.hdv_vertex: Vertex = None
        self.path_to_hdvMapId: list[Edge] = None

    def run(self, objectGID, quantityToSell) -> bool:
        self._logger.debug(f"Starting sell operation for item {objectGID} with quantity {quantityToSell}")
        
        if quantityToSell not in self.VALID_QUANTITIES:
            return self.finish(self.INVALID_QUANTITY_ERROR, f"Invalid quantity. Must be one of {self.VALID_QUANTITIES}")

        self.objectGID = objectGID
        self.quantityToSell = quantityToSell
        
        self._item_to_sell = self.getItem(objectGID)
        
        if not self._validate_initial_conditions():
            return False
        
        # Calculate total batches we can sell
        self._pending_quantity = self._item_to_sell.quantity
        
        self._logger.debug(f"Initial inventory quantity: {self._pending_quantity}")
        self._logger.debug(f"Will sell in batches of {self.quantityToSell}")
        
        self.on(KernelEvent.MessageReceived, self._on_message)
        
        self._logger.debug(f"Initial setup complete, traveling to HDV at {self.hdv_vertex.mapId if self.hdv_vertex else 'current map'}")

        if self.hdv_vertex != PlayedCharacterManager().currVertex:
            self.travelUsingZaap(self.hdv_vertex.mapId, self.hdv_vertex.zoneId, callback=self._on_bidhouse_map_reached)
        else:
            self._on_bidhouse_map_reached(None, None)
        return True

    def _validate_initial_conditions(self):
        self._logger.debug("Validating initial conditions...")
        
        if self._item_to_sell is None:
            return self.finish(self.OBJECT_NOT_FOUND_ERROR, "Unable to find object to sell in player inventory")

        self._logger.debug(f"Found item in inventory: {self._item_to_sell.objectGID} (quantity: {self._item_to_sell.quantity})")
        
        if self._item_to_sell.quantity < self.quantityToSell:
            return self.finish(self.INVALID_QUANTITY_ERROR, "Not enough carried quantity to sell item")
        
        self._hdv_gfx_id = self.ITEM_TYPE_TO_MARKETPLACE_GFX_ID_MAP.get(self._item_to_sell.category)
        self._logger.debug(f"Item category: {self._item_to_sell.category}, HDV GFX ID: {self._hdv_gfx_id}")
        
        if not self._hdv_gfx_id:
            return self.finish(self.CANT_LOCATE_HDV_ERROR, f"Cant find hdv gfx so cant locate it")
        
        self.path_to_hdvMapId = Localizer.findClosestHintMapByGfx(PlayedCharacterManager().currentMap.mapId, self._hdv_gfx_id)
        
        if self.path_to_hdvMapId is None:
            return self.finish(self.CANT_LOCATE_HDV_ERROR, f"Cant find a reachable hdv map id from its gfx")

        if len(self.path_to_hdvMapId) == 0:
            self.hdv_vertex = PlayedCharacterManager().currVertex
        else:
            self.hdv_vertex = self.path_to_hdvMapId[-1].dst
        
        self._logger.debug("Initial validation successful")
        return True
        
    def _on_message(self, event, msg):
        """Handle server messages"""
        try:
            # Handle sell mode start
            if self._state == "SWITCHING_TO_SELL":
                if isinstance(msg, ExchangeStartedBidSellerMessage):
                    self._handle_sell_mode_started(msg)
                return
                
            # Handle search response before proceeding to price check
            if self._state == "SEARCHING":
                if isinstance(msg, ExchangeTypesItemsExchangerDescriptionForUserMessage):
                    if msg.objectGID == self.objectGID:
                        self._logger.debug(f"Received search response for GID: {msg.objectGID}")
                        self._prices_infos[msg.objectGID] = msg
                        self._state = "CHECKING_PRICE"
                        self.sendAskItemInfos()
                return
                        
            # Handle price response
            if self._state == "CHECKING_PRICE":
                if isinstance(msg, ExchangeBidPriceForSellerMessage):
                    if msg.genericId == self.objectGID:
                        self._handle_price_info(msg)
                return
                
            # Handle update sequence
            if self._state == "UPDATING":
                if isinstance(msg, (KamasUpdateMessage, ExchangeBidHouseItemRemoveOkMessage, 
                                ExchangeBidHouseItemAddOkMessage)):
                    self._handle_updating_sequence(msg)
                return

            # Handle selling sequence - include all relevant message types
            if self._state == "SELLING":
                if isinstance(msg, (ObjectQuantityMessage, ObjectDeletedMessage, KamasUpdateMessage, 
                                ExchangeBidHouseItemAddOkMessage, ExchangeBidHouseInListUpdatedMessage,
                                InventoryWeightMessage)):
                    self._handle_selling_sequence(msg)
                return

        except Exception as e:
            self._logger.error(f"Error in message handler: {e}")
            return self.finish(1, str(e))

    def _handle_selling_sequence(self, msg):
        """Handle the complete sequence of messages for putting item up for sale"""
        try:
            if isinstance(msg, ObjectDeletedMessage):
                self._selling_sequence_received.add("quantity")
                self._logger.debug("Item stack depleted from inventory")
                self._pending_quantity = 0  # No more items left
            elif isinstance(msg, ObjectQuantityMessage):
                self._selling_sequence_received.add("quantity")
                self._logger.debug(f"Updated inventory quantity: {msg.quantity}")
                self._pending_quantity = msg.quantity  # Update with new quantity
            elif isinstance(msg, KamasUpdateMessage):
                self._selling_sequence_received.add("kamas")
                self._logger.debug(f"Updated kamas: {msg.kamasTotal}")
            elif isinstance(msg, ExchangeBidHouseItemAddOkMessage):
                self._selling_sequence_received.add("add")
                self._last_sale_info = msg.itemInfo
                self._logger.debug(f"Sale confirmed: {msg.itemInfo.quantity}x at {msg.itemInfo.objectPrice}")
            elif isinstance(msg, ExchangeBidHouseInListUpdatedMessage):
                self._selling_sequence_received.add("list")
                self._logger.debug(f"Market listing updated for item {msg.objectGID}")
            elif isinstance(msg, InventoryWeightMessage):
                self._selling_sequence_received.add("weight")
                self._logger.debug("Inventory weight updated")
            
            # Check if we've received the complete sequence
            expected_sequence = {"quantity", "kamas", "add", "list", "weight"}
            if self._selling_sequence_received >= expected_sequence:
                self._logger.debug("Sale sequence complete!")
                self._selling_sequence_received.clear()
                
                # Track this bid in our session
                if self._last_sale_info:
                    self._session_bids.add(self._last_sale_info.objectUID)
                    self._sellBids.append(self._last_sale_info)
                    self._batches_sold += 1
                    
                    self._logger.debug(f"Bids placed this session: {len(self._session_bids)}/3")
                    self._logger.debug(f"Remaining quantity: {self._pending_quantity}")
                    
                    # Check if we should continue
                    if self._pending_quantity > 0 and len(self._session_bids) < 3:
                        self._check_remaining_inventory()
                    else:
                        if self._pending_quantity == 0:
                            self._logger.debug("No more items in inventory")
                        else:
                            self._logger.debug(f"Session bid limit reached with {self._pending_quantity} items remaining")
                        self.finish(0)
                else:
                    self._logger.error("Sale sequence completed but no sale info received")
                    self.finish(1)

        except Exception as e:
            self._logger.error(f"Error in selling sequence: {e}")
            return self.finish(1, str(e))

    def _check_remaining_inventory(self):
        """Check if we have more items to sell and continue if we do"""
        # Refresh item from inventory as quantity may have changed
        self._item_to_sell = self.getItem(self.objectGID)
        
        if not self._item_to_sell or self._item_to_sell.quantity < self.quantityToSell:
            self._logger.debug("No more items to sell in inventory, finishing")
            self.finish(0)
            return
            
        # Use the tracked pending quantity instead of recalculating
        self._logger.debug(f"Found more items to sell in inventory: {self._pending_quantity}")
        
        # If we have recent prices (less than 30 seconds old), use them
        if self._current_min_price and time.time() - self._last_price_check < 30:
            self._logger.debug("Using cached price information")
            self._process_price_action()
        else:
            # Need fresh price info
            self._state = "SEARCHING"
            self.sendSearchItem()
        
    def _handle_sell_mode_started(self, msg: ExchangeStartedBidSellerMessage):
        """Handle transition to sell mode and check existing bids"""
        self._logger.debug("HDV sell mode started, initializing sale process...")
        self._sellerDescriptor = msg.sellerDescriptor
        self._sellBids = msg.objectsInfos
        self._tax_percentage = msg.sellerDescriptor.taxPercentage
        
        # Log existing bids for our item/quantity
        existing_bids = [bid for bid in self._sellBids 
                        if bid.objectGID == self.objectGID and 
                        bid.quantity == self.quantityToSell]
        
        for bid in existing_bids:
            hours_remaining = bid.unsoldDelay // 3600
            minutes_remaining = (bid.unsoldDelay % 3600) // 60
            self._logger.debug(f"Found existing bid: {bid.quantity}x item {bid.objectGID}")
            self._logger.debug(f"Time until expiry: {hours_remaining}h {minutes_remaining}m")
        
        if existing_bids:
            self._logger.debug(f"Found {len(existing_bids)} existing bids")
            # Start with price check
            self._state = "SEARCHING"
            self.sendSearchItem()
        else:
            self._logger.debug("No existing bids found for this item/quantity")
            self._start_new_sale_process()

    def _start_new_sale_process(self):
        """Start sale process by searching for item"""
        self._logger.debug("Starting new sale sequence")
        self._state = "SEARCHING"  # Changed from CHECKING_ITEM to be more explicit
        self.sendSearchItem()

    def _process_next_update(self):
        """Process next pending bid update if not currently processing one"""
        self._logger.debug("Processing next update if any...")
        if not self._current_update and self._pending_updates:
            self._current_update = self._pending_updates.pop(0)
            self._state = "CHECKING_PRICE"
            self.sendAskItemInfos()
        else:
            # Check inventory for new sales after updates are done
            self._check_remaining_inventory()

    def _handle_price_info(self, msg):
        """Handle price info response and compare with current bid if updating"""
        self._logger.debug(f"Received price info for item {msg.genericId}")
        
        try:
            # Cache the prices
            quantity_index = self.VALID_QUANTITIES.index(self.quantityToSell)
            self._current_min_price = msg.minimalPrices[quantity_index]
            self._current_avg_price = msg.averagePrice * self.quantityToSell
            self._last_price_check = time.time()
            
            self._logger.debug(f"Price analysis - Min: {self._current_min_price}, Avg: {self._current_avg_price}")
            
            # Now process the action based on cached prices
            self._process_price_action()
                    
        except Exception as e:
            self._logger.error(f"Error processing price info: {e}")
            return self.finish(1, f"Error processing price info: {str(e)}")

    def _process_price_action(self):
        """Process actions based on current prices"""
        try:
            min_profitable_price = int(self._current_avg_price * self.MIN_PRICE_THRESHOLD)
            
            # Find our lowest price among existing bids
            our_lowest_price = float('inf')
            
            # Count only bids we made in this session
            session_bid_count = len(self._session_bids)
            
            self._logger.debug(f"Bids made in this session: {session_bid_count}")
            
            for bid in self._sellBids:
                if bid.objectGID == self.objectGID and bid.quantity == self.quantityToSell:
                    our_lowest_price = min(our_lowest_price, bid.objectPrice)
            
            target_price = self._current_min_price if self._current_min_price == our_lowest_price else self._current_min_price - 1
            target_price = max(target_price, min_profitable_price)
            
            self._logger.debug(f"Price evaluation - Market min: {self._current_min_price}, Our lowest: {our_lowest_price}")
            self._logger.debug(f"Target price: {target_price}, Min acceptable: {min_profitable_price}")
            
            if self._current_min_price >= min_profitable_price:
                if self._current_update:  # Handling bid update
                    # Update logic remains the same...
                    current_bid_price = self._current_update.objectPrice
                    
                    if current_bid_price <= self._current_min_price:
                        self._logger.debug(f"Our price ({current_bid_price}) is already at/below minimum, skipping update")
                        self._current_update = None
                        self._process_next_update()
                        return

                    price_diff = current_bid_price - target_price
                    if price_diff <= max(int(current_bid_price * 0.01), 2):
                        self._logger.debug(f"Price difference too small ({price_diff}), skipping update")
                        self._current_update = None
                        self._process_next_update()
                        return

                    if self._can_afford_tax(target_price):
                        self._state = "UPDATING"
                        self.sendEditSellBid(self._current_update.objectUID, self.quantityToSell, target_price)
                    else:
                        self._logger.debug("Cannot afford tax for update")
                        self._current_update = None
                        self._process_next_update()
                else:  # Handling new sale
                    # Check if we've hit the maximum listings for this session
                    if session_bid_count >= 3:
                        self._logger.debug(f"Already placed {session_bid_count} bids in this session, finishing")
                        self.finish(0)
                        return
                    
                    # Process new sale if we can afford it
                    if self._can_afford_tax(target_price):
                        self._state = "SELLING"
                        self._logger.debug(f"Putting batch {session_bid_count + 1}/3 up for sale at price: {target_price}")
                        Kernel().worker.terminated.wait(2)
                        self.sendPutUpForSale(target_price)
                    else:
                        self._logger.debug("Cannot afford tax for new sale")
                        self.finish(self.NOT_ENOUGH_KAMAS_TO_PAY_TAX)
            else:
                self._logger.debug(f"Market price ({self._current_min_price}) below minimum profitable price ({min_profitable_price})")
                self.finish(0)

        except Exception as e:
            self._logger.error(f"Error in price action: {e}")
            return self.finish(1, str(e))

    def _handle_new_sale(self, current_min_price, average_price):
        """Handle putting item up for sale"""
        try:
            # Calculate prices
            min_profitable_price = int(average_price * self.MIN_PRICE_THRESHOLD)
            target_price = max(min_profitable_price, current_min_price - 1)
            
            self._logger.debug(f"Sale price analysis - Target: {target_price}, Min acceptable: {min_profitable_price}")
            
            if current_min_price >= min_profitable_price:
                if self._can_afford_tax(target_price):
                    self._state = "SELLING"
                    self._logger.debug(f"Putting item up for sale at price: {target_price}")
                    Kernel().worker.terminated.wait(2)
                    self.sendPutUpForSale(target_price)
                else:
                    return self.finish(self.NOT_ENOUGH_KAMAS_TO_PAY_TAX, "Not enough kamas to pay tax")
            else:
                self._logger.debug(f"Market price ({current_min_price}) below minimum profitable price ({min_profitable_price})")
                self.finish(0)
                
        except Exception as e:
            self._logger.error(f"Error handling new sale: {e}")
            return self.finish(1, f"Error handling new sale: {str(e)}")

    def _can_afford_tax(self, price):
        tax_amount = (price * self._tax_percentage) / 100
        current_kamas = PlayedCharacterManager().characteristics.kamas
        can_afford = current_kamas >= tax_amount
        
        self._logger.debug(f"Tax check - Price: {price}, Tax %: {self._tax_percentage}, Tax Amount: {tax_amount}")
        self._logger.debug(f"Current kamas: {current_kamas}, Can afford: {can_afford}")
        
        return can_afford

    def _handle_updating_sequence(self, msg):
        """Handle the bid update message sequence"""
        try:
            if isinstance(msg, KamasUpdateMessage):
                self._updating_sequence_received.add("kamas")
                self._logger.debug(f"Updated kamas after bid update: {msg.kamasTotal}")
            elif isinstance(msg, ExchangeBidHouseItemRemoveOkMessage):
                self._updating_sequence_received.add("remove")
                self._logger.debug("Old bid removed")
            elif isinstance(msg, ExchangeBidHouseItemAddOkMessage):
                self._updating_sequence_received.add("add")
                self._last_sale_info = msg.itemInfo
                self._logger.debug(f"New bid added: {msg.itemInfo.quantity}x at {msg.itemInfo.objectPrice}")
                
                # Consider sequence complete after add message and move to next update
                self._logger.debug("Bid update sequence complete!")
                self._updating_sequence_received.clear()
                self._current_update = None
                self._process_next_update()
                
        except Exception as e:
            self._logger.error(f"Error in update sequence: {e}")
            return self.finish(1, str(e))

    def _open_hdv(self):
        self._logger.debug("Opening marketplace...")
        if self._item_to_sell.category == ItemCategoryEnum.RESOURCES_CATEGORY:
            hdvElement = Kernel().interactiveFrame.getIeByTypeId(self.RESOURCE_MARKETPLACE_ELEMENT_TYPE_ID)
            if not hdvElement:
                self.finish(self.CANT_LOCATE_HDV_ERROR, f"Couldn't locate hdv interactive element using its type id!")
                return
            self.useSkill(
                ie=hdvElement,
                waitForSkillUsed=False,
                callback=self._on_bidhouse_open,
            )
        else: 
            self.finish(self.CANT_LOCATE_HDV_ERROR, f"Bot don't know how to find bidhouse of item category {self._item_to_sell.category}")
        
    def _on_bidhouse_map_reached(self, code, err):
        if err:
            return self.finish(code, err)
        self._state = "OPENING_HDV"
        self._open_hdv()
    
    def _on_bidhouse_open(self, code, err):
        if err:
            return self.finish(code, err)
        self._state = "SWITCHING_TO_SELL"
        self._switch_to_sell_mode()
    
    def _switch_to_sell_mode(self):
        self._state = "SWITCHING_TO_SELL"  # Set state before sending message
        self._logger.debug("Switching to sell mode...")
        msg = NpcGenericActionRequestMessage()
        msg.init(-1, self.SELL_MODE_ACTION_ID, self.hdv_vertex.mapId)
        ConnectionsHandler().send(msg)

    def getItem(self, objectGID) -> ItemWrapper:
        iw = ItemWrapper._cacheGId.get(objectGID)
        if iw:
            return iw
        for iw in InventoryManager().inventory.getView("real").content:
            if iw.objectGID == objectGID:
                return iw
        return None

    def sendSearchItem(self):
        """Reset sequence and send search request"""
        msg = ExchangeBidHouseSearchMessage()
        msg.init(self._item_to_sell.objectGID, True)
        ConnectionsHandler().send(msg)

    def sendAskItemInfos(self):
        """Send price request without clearing sequence"""
        msg = ExchangeBidHousePriceMessage()
        msg.init(self._item_to_sell.objectGID)
        ConnectionsHandler().send(msg)

    def sendPutUpForSale(self, price):
        """Send new sale with inventory item UID"""
        self._logger.info(f"New sale - UID: {self._item_to_sell.objectUID}, quantity: {self.quantityToSell}, price: {price}")
        msg = ExchangeObjectMovePricedMessage()
        msg.init(price, self._item_to_sell.objectUID, self.quantityToSell)
        ConnectionsHandler().send(msg)

    def sendEditSellBid(self, objectUID, quantity, new_price):
        """Send bid update with specific object UID"""
        self._logger.info(f"Updating bid - UID: {objectUID}, quantity: {quantity}, new price: {new_price}")
        msg = ExchangeObjectModifyPricedMessage()
        msg.init(new_price, objectUID, quantity)
        ConnectionsHandler().send(msg)