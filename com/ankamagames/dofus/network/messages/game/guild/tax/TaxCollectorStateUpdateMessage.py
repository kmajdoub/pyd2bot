from com.ankamagames.dofus.network.messages.NetworkMessage import NetworkMessage


class TaxCollectorStateUpdateMessage(NetworkMessage):
    protocolId = 7095
    uniqueId:int
    state:int
    
    
