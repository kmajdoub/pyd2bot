from com.ankamagames.dofus.network.messages.game.context.roleplay.party.AbstractPartyMessage import (
    AbstractPartyMessage,
)


class PartyInvitationDetailsRequestMessage(AbstractPartyMessage):
    def init(self, partyId_: int):

        super().__init__(partyId_)
