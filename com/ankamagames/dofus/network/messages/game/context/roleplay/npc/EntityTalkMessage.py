from com.ankamagames.dofus.network.messages.NetworkMessage import NetworkMessage


class EntityTalkMessage(NetworkMessage):
    protocolId = 4321
    entityId:int
    textId:int
    parameters:str
    
    
