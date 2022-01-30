from com.ankamagames.dofus.network.messages.NetworkMessage import NetworkMessage


class ActorRestrictionsInformations(NetworkMessage):
    protocolId = 8982
    cantBeAggressed:bool
    cantBeChallenged:bool
    cantTrade:bool
    cantBeAttackedByMutant:bool
    cantRun:bool
    forceSlowWalk:bool
    cantMinimize:bool
    cantMove:bool
    cantAggress:bool
    cantChallenge:bool
    cantExchange:bool
    cantAttack:bool
    cantChat:bool
    cantBeMerchant:bool
    cantUseObject:bool
    cantUseTaxCollector:bool
    cantUseInteractive:bool
    cantSpeakToNPC:bool
    cantChangeZone:bool
    cantAttackMonster:bool
    
    
