from com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeObjectMessage import ExchangeObjectMessage
from com.ankamagames.dofus.network.types.game.data.items.ObjectItem import ObjectItem


class ExchangeObjectModifiedInBagMessage(ExchangeObjectMessage):
    protocolId = 1456
    object:ObjectItem
    
