from Grinder.models import Character
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.misc.BotEventsManager import BotEventsManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.berilia.managers.Listener import Listener
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.party.PartyMemberInformations import \
    PartyMemberInformations
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class PartyLeader(AbstractBehavior):
    ASK_INVITE_TIMOUT = 20
    CONFIRME_JOIN_TIMEOUT = 20

    def __init__(self, followers: list[Character]) -> None:
        super().__init__()
        self.followers = followers

    @property
    def partyMembers(self):
        return Kernel().partyFrame.partyMembers
    
    @property
    def currentPartyId(self):
        return Kernel().partyFrame.currentPartyId
    
    @property
    def allFollowersJoinedParty(self):
        for follower in self.followers:
            if follower.id not in self.partyMembers:
                return False
        return True
    
    def run(self):
        self.wantedDeleteParty = False
        self.expectingMemberLeave = set()
        self.partyJoinListeners = dict[str, Listener]()
        KernelEventsManager().on(KernelEvent.PartyInvited, self.onPartyInvitation, originator=self)
        KernelEventsManager().on(KernelEvent.PartyDeleted, self.onPartyDeleted, originator=self)
        KernelEventsManager().on(KernelEvent.MemberLeftParty, self.onMemberLeft, originator=self)
        KernelEventsManager().on(KernelEvent.IJoinedParty, self.onPartyJoin, originator=self)
        self.inviteFollowers()
    
    def onPartyJoin(self, event, partyId, members: list[PartyMemberInformations]):
        membersNotInParty = filter(lambda follower: follower.id not in self.partyMembers, self.followers)
        for follower in membersNotInParty:
            if follower.id not in self.partyJoinListeners:
                self.inviteFollower(follower.id)

    def onMemberLeft(self, event, member: PartyMemberInformations):
        Logger().debug(f"{member.name} left the party")
        if member.id not in self.expectingMemberLeave:
            Logger().warning(f"Member {member.name} left party unexpectedly!")
            self.inviteFollower(member.id)
        else:
            self.expectingMemberLeave.remove(member.id)

    def onPartyDeleted(self, event, partyId):
        if not self.wantedDeleteParty:
            Logger().error("Party deleted unexpectedly!")
            self.inviteFollowers()
        else:
            self.wantedDeleteParty = False
    
    def inviteFollowers(self):
        for follower in self.followers:
            self.inviteFollower(follower.id)
            if Kernel().worker.terminated.wait(0.2):
                return

    def cancelPartyInvite(self, memberId):
        if self.currentPartyId is not None:
            if memberId in self.partyJoinListeners:
                self.partyJoinListeners[memberId].delete()
            Kernel().partyFrame.sendPartyInviteCancel(memberId)

    def onFollowerJoinedParty(self, memberId):
        Kernel().partyFrame.sendFollowMember(memberId)
        del self.partyJoinListeners[memberId]
        if self.allFollowersJoinedParty:
            BotEventsManager().send(BotEventsManager.ALL_MEMBERS_JOINED_PARTY)

    def onFollowerPartyInviteTimeout(self, listener:Listener, memberId):
        Logger().info(f"Follower ({memberId}) invitation accept timeout")
        listener.armTimer()
    
    def inviteFollower(self, memberId):
        if self.partyJoinListeners.get(memberId):
            self.cancelPartyInvite(memberId)
        if memberId not in self.partyMembers:
            self.partyJoinListeners[memberId] = KernelEventsManager().onceMemberJoinedParty(
                memberId,
                lambda: self.onFollowerJoinedParty(memberId),
                timeout=self.CONFIRME_JOIN_TIMEOUT, 
                ontimeout=lambda l: self.onFollowerPartyInviteTimeout(l, memberId),
                originator=self
            )
            for member in self.followers:
                if member.id == memberId:
                    Logger().warning(f"Player {member.name} is already in party")
                    Kernel().partyFrame.sendPartyInviteRequest(member.name)
                    Logger().debug(f"Join party invitation sent to {member.name}")
        else:
            Logger().warning(f"wants to invite a player already in party")

    def onPartyInvitation(self, event, partyId, partyType, fromId, fromName):
        Logger().warning(f"Refuse party invite from player ({fromName})")
        Kernel().partyFrame.sendRefusePartyinvite(partyId)
