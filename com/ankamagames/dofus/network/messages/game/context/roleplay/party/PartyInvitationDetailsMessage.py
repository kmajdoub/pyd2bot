from com.ankamagames.dofus.network.messages.game.context.roleplay.party.AbstractPartyMessage import AbstractPartyMessage
from com.ankamagames.dofus.network.types.game.context.roleplay.party.PartyInvitationMemberInformations import PartyInvitationMemberInformations
from com.ankamagames.dofus.network.types.game.context.roleplay.party.PartyGuestInformations import PartyGuestInformations


class PartyInvitationDetailsMessage(AbstractPartyMessage):
    protocolId = 3615
    partyType:int
    partyName:str
    fromId:float
    fromName:str
    leaderId:float
    members:list[PartyInvitationMemberInformations]
    guests:list[PartyGuestInformations]
    
