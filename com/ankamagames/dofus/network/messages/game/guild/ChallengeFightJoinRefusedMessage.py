from com.ankamagames.dofus.network.messages.NetworkMessage import NetworkMessage


class ChallengeFightJoinRefusedMessage(NetworkMessage):
    protocolId = 2066
    playerId:float
    reason:int
    
