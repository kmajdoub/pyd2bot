from com.ankamagames.dofus.network.messages.NetworkMessage import NetworkMessage


class AbstractFightDispellableEffect(NetworkMessage):
    protocolId = 1657
    uid:int
    targetId:int
    turnDuration:int
    dispelable:int
    spellId:int
    effectId:int
    parentBoostUid:int
    
    
