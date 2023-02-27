from typing import TYPE_CHECKING

from pyd2bot.logic.common.frames.BotRPCFrame import BotRPCFrame
from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.logic.roleplay.behaviors.AutoTrip import AutoTrip
from pyd2bot.logic.roleplay.behaviors.ChangeMap import ChangeMap
from pyd2bot.logic.roleplay.messages.LeaderPosMessage import LeaderPosMessage
from pyd2bot.logic.roleplay.messages.LeaderTransitionMessage import \
    LeaderTransitionMessage
from pyd2bot.misc.BotEventsmanager import BotEventsManager
from pyd2bot.thriftServer.pyd2botService.ttypes import Character
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import \
    MapDisplayManager
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import (
    KernelEvent, KernelEventsManager)
from pydofus2.com.ankamagames.dofus.datacenter.communication.InfoMessage import \
    InfoMessage
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Transition import \
    Transition
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import \
    Vertex
from pydofus2.com.ankamagames.dofus.network.enums.PartyJoinErrorEnum import \
    PartyJoinErrorEnum
from pydofus2.com.ankamagames.dofus.network.enums.TextInformationTypeEnum import \
    TextInformationTypeEnum
from pydofus2.com.ankamagames.dofus.network.messages.game.atlas.compass.CompassUpdatePartyMemberMessage import \
    CompassUpdatePartyMemberMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.basic.TextInformationMessage import \
    TextInformationMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightJoinRequestMessage import \
    GameFightJoinRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapInformationsRequestMessage import \
    MapInformationsRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyAcceptInvitationMessage import \
    PartyAcceptInvitationMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyCancelInvitationMessage import \
    PartyCancelInvitationMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyCannotJoinErrorMessage import \
    PartyCannotJoinErrorMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyDeletedMessage import \
    PartyDeletedMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyFollowMemberRequestMessage import \
    PartyFollowMemberRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyInvitationMessage import \
    PartyInvitationMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyInvitationRequestMessage import \
    PartyInvitationRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyJoinMessage import \
    PartyJoinMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyLeaveRequestMessage import \
    PartyLeaveRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyMemberInStandardFightMessage import \
    PartyMemberInStandardFightMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyMemberRemoveMessage import \
    PartyMemberRemoveMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyNewGuestMessage import \
    PartyNewGuestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyNewMemberMessage import \
    PartyNewMemberMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyRefuseInvitationMessage import \
    PartyRefuseInvitationMessage
from pydofus2.com.ankamagames.dofus.network.types.common.PlayerSearchCharacterNameInformation import \
    PlayerSearchCharacterNameInformation
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.party.PartyMemberInformations import \
    PartyMemberInformations
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import \
    BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.data.I18n import I18n
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority

if TYPE_CHECKING:
    from pyd2bot.logic.roleplay.behaviors.FarmPath import FarmPath
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayEntitiesFrame import \
        RoleplayEntitiesFrame
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayMovementFrame import \
        RoleplayMovementFrame


class BotPartyFrame(Frame):
    ASK_INVITE_TIMOUT = 20
    CONFIRME_JOIN_TIMEOUT = 20

    def __init__(self) -> None:
        super().__init__()

    @property
    def isLeader(self):
        return BotConfig().isLeader

    @property
    def followers(self) -> list[Character]:
        return BotConfig().followers

    @property
    def leaderName(self):
        return BotConfig().character.name if self.isLeader else BotConfig().leader.name

    @property
    def priority(self) -> int:
        return Priority.VERY_LOW

    @property
    def movementFrame(self) -> "RoleplayMovementFrame":
        return Kernel().worker.getFrameByName("RoleplayMovementFrame")

    @property
    def entitiesFrame(self) -> "RoleplayEntitiesFrame":
        return Kernel().worker.getFrameByName("RoleplayEntitiesFrame")

    @property
    def farmFrame(self) -> "FarmPath":
        return Kernel().worker.getFrameByName("BotFarmPathFrame")

    @property
    def rpcFrame(self) -> "BotRPCFrame":
        return Kernel().worker.getFrameByName("BotRPCFrame")

    @property
    def leader(self) -> Character:
        return BotConfig().leader

    @property
    def allMembersOnSameMap(self):
        for follower in self.followers:
            if self.entitiesFrame is None:
                return False
            entity = self.entitiesFrame.getEntityInfos(follower.id)
            if not entity:
                return False
        Logger().info(f"[BotPartyFrame] All members are on the same map")
        return True

    def checkAllMembersIdle(self):
        self.allMembersIdle = False
        self._followerStatus = {follower.login: None for follower in self.followers}
        for member in self.followers:
            self.rpcFrame.askForStatus(member.login, self.onFollowerStatus)

    def onFollowerStatus(self, result: str, error: str, sender: str):
        if error is not None:
            raise Exception(f"Error while fetching follower status: {error}")
        self._followerStatus[sender] = result
        if all(status is not None for status in self._followerStatus.values()):
            nonIdleMemberNames = [f"{name}:{status}" for name, status in self._followerStatus.items() if status != "idle"]
            if nonIdleMemberNames:
                Logger().info(f"[BotPartyFrame] Waiting for members {nonIdleMemberNames}.")
                Kernel().worker.terminated.wait(1)
                self.checkAllMembersIdle()
            else:
                Logger().info(f"[BotPartyFrame] All members are idle.")
                self.allMembersIdle = False
                BotEventsManager().send(BotEventsManager.ALL_PARTY_MEMBERS_IDLE)

    def pulled(self):
        self.leaveParty()
        self.partyMembers.clear()
        if self.partyInviteTimers:
            for timer in self.partyInviteTimers.values():
                timer.cancel()
        self.currentPartyId = None
        self.partyInviteTimers.clear()
        return True

    def pushed(self):
        self.allMembersJoinedParty = False
        self.allMembersIdle = False
        self.partyInviteTimers = dict[str, BenchmarkTimer]()
        self.currentPartyId = None
        self.partyMembers = dict[int, PartyMemberInformations]()
        self.joiningLeaderVertex: Vertex = None
        self.JoinFightRequestTimer = None
        self.joiningFightId = None
        self.followingLeaderTransition = None
        self._followerStatus = {follower.login: None for follower in self.followers}
        return True

    def inviteAllFollowers(self):
        for follower in self.followers:
            self.sendPartyInvite(follower.name)
            Kernel().worker.terminated.wait(0.2)

    def getPartyMemberById(self, id: int) -> Character:
        for follower in self.followers:
            if int(follower.id) == int(id):
                return follower
        if int(id) == int(self.leader.id):
            return self.leader
        return None

    def getPartyMemberByName(self, name: str) -> Character:
        for follower in self.followers:
            if follower.name == name:
                return follower
        return None

    def cancelPartyInvite(self, playerName):
        follower = self.getPartyMemberByName(playerName)
        if follower and self.currentPartyId is not None:
            cpimsg = PartyCancelInvitationMessage()
            cpimsg.init(follower.id, self.currentPartyId)
            ConnectionsHandler().send(cpimsg)
            return True
        return False

    def sendPartyInvite(self, playerName):
        if self.partyInviteTimers.get(playerName):
            self.partyInviteTimers[playerName].cancel()
            self.cancelPartyInvite(playerName)
        follower = self.getPartyMemberByName(playerName)
        if follower.id not in self.partyMembers:
            pimsg = PartyInvitationRequestMessage()
            pscni = PlayerSearchCharacterNameInformation()
            pscni.init(playerName)
            pimsg.init(pscni)
            ConnectionsHandler().send(pimsg)
            self.partyInviteTimers[playerName] = BenchmarkTimer(
                self.CONFIRME_JOIN_TIMEOUT, self.sendPartyInvite, [playerName]
            )
            self.partyInviteTimers[playerName].start()
            Logger().debug(f"[BotPartyFrame] Join party invitation sent to {playerName}")

    def sendFollowMember(self, memberId):
        pfmrm = PartyFollowMemberRequestMessage()
        pfmrm.init(memberId, self.currentPartyId)
        ConnectionsHandler().send(pfmrm)

    def joinFight(self, fightId: int):
        def ontimeout() -> None:
            Logger().error("Join fight request timeout")
        self.JoinFightRequestTimer = BenchmarkTimer(10, ontimeout)
        def onfight(event_id) -> None:
            if self.JoinFightRequestTimer:
                self.JoinFightRequestTimer.cancel()
            self.JoinFightRequestTimer = None
            self.joiningFightId = None
        KernelEventsManager().once(KernelEvent.FIGHT_STARTED, onfight)
        gfjrmsg = GameFightJoinRequestMessage()
        gfjrmsg.init(self.leader.id, fightId)
        self.JoinFightRequestTimer.start()
        self.joiningFightId = fightId
        ConnectionsHandler().send(gfjrmsg)

    def checkIfTeamInFight(self):
        if not PlayedCharacterManager().isFighting and self.entitiesFrame:
            for fightId, fight in self.entitiesFrame._fights.items():
                for team in fight.teams:
                    for member in team.teamInfos.teamMembers:
                        if member.id in self.partyMembers:
                            Logger().debug(f"[BotPartyFrame] Team is in a fight")
                            self.joinFight(fightId)
                            return

    def leaveParty(self):
        if self.currentPartyId is None:
            Logger().warning("[BotPartyFrame] No party to leave")
            return
        if ConnectionsHandler().conn:
            plmsg = PartyLeaveRequestMessage()
            plmsg.init(self.currentPartyId)
            ConnectionsHandler().send(plmsg)
        self.currentPartyId = None

    def process(self, msg: Message):

        if isinstance(msg, PartyNewGuestMessage):
            return True

        elif isinstance(msg, PartyMemberRemoveMessage):
            member = self.getPartyMemberById(msg.leavingPlayerId)
            Logger().debug(f"[BotPartyFrame] {member.name} left the party")
            player = self.partyMembers.get(msg.leavingPlayerId)
            self.allMembersJoinedParty = False
            if player:
                del self.partyMembers[msg.leavingPlayerId]
            if self.isLeader:
                self.sendPartyInvite(member.name)
            return True

        elif isinstance(msg, PartyDeletedMessage):
            self.currentPartyId = None
            self.partyMembers.clear()
            if self.isLeader:
                for follower in self.followers:
                    self.sendPartyInvite(follower.name)
            return True

        elif isinstance(msg, PartyInvitationMessage):
            notifText = (
                I18n.getUiText("ui.common.invitation")
                + " "
                + I18n.getUiText("ui.party.playerInvitation", [f"player,{msg.fromId}::{msg.fromName}"])
            )
            Logger().debug(f"[BotPartyFrame] {notifText}.")
            if not self.isLeader and int(msg.fromId) == int(self.leader.id):
                paimsg = PartyAcceptInvitationMessage()
                paimsg.init(msg.partyId)
                ConnectionsHandler().send(paimsg)
                Logger().debug(f"[BotPartyFrame] Accepted party invite from '{msg.fromName}'.")
            else:
                pirmsg = PartyRefuseInvitationMessage()
                pirmsg.init(msg.partyId)
                ConnectionsHandler().send(pirmsg)
            return True

        elif isinstance(msg, PartyNewMemberMessage):
            member = msg.memberInformations
            Logger().info(f"[BotPartyFrame] '{member.name}' joined your party.")
            self.currentPartyId = msg.partyId
            self.partyMembers[member.id] = member
            if member.id != PlayedCharacterManager().id and self.isLeader:
                self.sendFollowMember(member.id)
                if member.name in self.partyInviteTimers:
                    self.partyInviteTimers[member.name].cancel()
                    del self.partyInviteTimers[member.name]
                    if not self.partyInviteTimers:
                        self.allMembersJoinedParty = True
                        BotEventsManager().send(BotEventsManager.ALL_MEMBERS_JOINED_PARTY)
            elif member.id == PlayedCharacterManager().id:
                self.sendFollowMember(self.leader.id)
            return True

        elif isinstance(msg, PartyJoinMessage):
            self.partyMembers.clear()
            Logger().debug(f"[BotPartyFrame] Joined Party {msg.partyId} of leader {msg.partyLeaderId}")
            for member in msg.members:
                if member.id not in self.partyMembers:
                    self.partyMembers[member.id] = member
                    if self.isLeader and member.name in self.partyInviteTimers:
                        self.partyInviteTimers[member.name].cancel()
                        del self.partyInviteTimers[member.name]
                if member.id == PlayedCharacterManager().id:
                    if self.currentPartyId is None:
                        self.currentPartyId = msg.partyId
                        if not self.isLeader:
                            self.sendFollowMember(self.leader.id)
            if self.isLeader:
                membersNotInParty = [follower for follower in self.followers if follower.id not in self.partyMembers]
                if not membersNotInParty:
                    self.allMembersJoinedParty = True
                else:
                    self.allMembersJoinedParty = False
                    for follower in membersNotInParty:
                        if follower.name not in self.partyInviteTimers:
                            self.sendPartyInvite(follower.name)
            if not self.isLeader and self.leader.id not in self.partyMembers:
                self.leaveParty()
                return
            self.checkIfTeamInFight()
            return True

        elif isinstance(msg, LeaderTransitionMessage):
            if msg.transition.transitionMapId == PlayedCharacterManager().currentMap.mapId:
                Logger().warning(
                    f"[BotPartyFrame] Leader '{self.leader.name}' is heading to my current map '{msg.transition.transitionMapId}', nothing to do."
                )
            else:
                Logger().info(f"[BotPartyFrame] Will follow '{self.leader.name}'")
                self.followingLeaderTransition = msg.transition
                def onresp(status, error):
                    self.followingLeaderTransition = None
                    if error is not None:
                        raise Exception(f"[BotPartyFrame] Error while following leader: {error}")
                ChangeMap().start(transition=msg.transition, dstMapId=msg.dstMapId, callback=onresp)
            return True

        elif isinstance(msg, LeaderPosMessage):
            self.leaderCurrVertex = msg.vertex
            if self.joiningLeaderVertex is not None and msg.vertex.UID != self.joiningLeaderVertex.UID:
                Logger().error(
                    f"[BotPartyFrame] Still following leader pos."
                )
            elif (
                PlayedCharacterManager().currVertex is not None
                and PlayedCharacterManager().currVertex.UID != msg.vertex.UID
            ):
                Logger().info(f"[BotPartyFrame] Leader {self.leaderName} is in vertex {msg.vertex}, will follow it.")
                self.joiningLeaderVertex = msg.vertex
                def onLeaderPosReached(status, error):
                    if error is not None:
                        raise Exception(f"[BotPartyFrame] Error while following leader: {error}")
                    self.joiningLeaderVertex = None
                AutoTrip().start(msg.vertex.mapId, msg.vertex.zoneId, onLeaderPosReached)
            else:
                Logger().warning(f"[BotPartyFrame] Leader {self.leaderName} is in vertex {msg.vertex}, nothing to do.")
            return True

        elif isinstance(msg, CompassUpdatePartyMemberMessage):
            if msg.memberId in self.partyMembers:
                self.partyMembers[msg.memberId].worldX = msg.coords.worldX
                self.partyMembers[msg.memberId].worldY = msg.coords.worldY
            else:
                Logger().error(f"[BotPartyFrame] Seems ig we are in party but not modeled yet in party frame")
                self.leaveParty()
            return True

        elif isinstance(msg, PartyMemberInStandardFightMessage):
            if float(msg.memberId) == float(self.leader.id):
                Logger().info(f"[BotPartyFrame] member {msg.memberId} started fight {msg.fightId}")
                if msg.fightMap.mapId != PlayedCharacterManager().currentMap.mapId:
                    def onmapreached(status, error):
                        if error:
                            raise Exception(f"[BotPartyFrame] Error while joining leader fight: {error}")
                        self.joinFight(msg.fightId)
                    AutoTrip().start(msg.fightMap.mapId, 1, onmapreached)
                else:
                    self.joinFight(msg.fightId)
            return True

        if isinstance(msg, PartyCannotJoinErrorMessage):
            pcjenmsg = msg
            reasonText = ""
            if pcjenmsg.reason == PartyJoinErrorEnum.PARTY_JOIN_ERROR_PARTY_FULL:
                reasonText = I18n.getUiText("ui.party.partyFull")
            elif pcjenmsg.reason == PartyJoinErrorEnum.PARTY_JOIN_ERROR_PARTY_NOT_FOUND:
                reasonText = I18n.getUiText("ui.party.cantFindParty")
            elif pcjenmsg.reason == PartyJoinErrorEnum.PARTY_JOIN_ERROR_PLAYER_BUSY:
                reasonText = I18n.getUiText("ui.party.cantInvitPlayerBusy")
            elif pcjenmsg.reason == PartyJoinErrorEnum.PARTY_JOIN_ERROR_PLAYER_NOT_FOUND:
                reasonText = I18n.getUiText("ui.common.playerNotFound", ["member"])
            elif pcjenmsg.reason in (
                PartyJoinErrorEnum.PARTY_JOIN_ERROR_UNMET_CRITERION,
                PartyJoinErrorEnum.PARTY_JOIN_ERROR_PLAYER_LOYAL,
            ):
                pass
            elif pcjenmsg.reason == PartyJoinErrorEnum.PARTY_JOIN_ERROR_PLAYER_TOO_SOLLICITED:
                reasonText = I18n.getUiText("ui.party.playerTooSollicited")
            elif pcjenmsg.reason == PartyJoinErrorEnum.PARTY_JOIN_ERROR_UNMODIFIABLE:
                reasonText = I18n.getUiText("ui.party.partyUnmodifiable")
            elif pcjenmsg.reason == PartyJoinErrorEnum.PARTY_JOIN_ERROR_PLAYER_ALREADY_INVITED:
                reasonText = I18n.getUiText("ui.party.playerAlreayBeingInvited")
            elif pcjenmsg.reason == PartyJoinErrorEnum.PARTY_JOIN_ERROR_NOT_ENOUGH_ROOM:
                reasonText = I18n.getUiText("ui.party.notEnoughRoom")
            elif pcjenmsg.reason in (
                PartyJoinErrorEnum.PARTY_JOIN_ERROR_COMPOSITION_CHANGED,
                PartyJoinErrorEnum.PARTY_JOIN_ERROR_UNKNOWN,
            ):
                reasonText = I18n.getUiText("ui.party.cantInvit")
            Logger().warning(f"[BotPartyFrame] Can't join party: {reasonText}")
            return True
        
        elif isinstance(msg, TextInformationMessage):
            msgInfo = InfoMessage.getInfoMessageById(msg.msgType * 10000 + msg.msgId)
            if msgInfo:
                textId = msgInfo.textId
            else:
                if msg.msgType == TextInformationTypeEnum.TEXT_INFORMATION_ERROR:
                    textId = InfoMessage.getInfoMessageById(10231).textId
                else:
                    textId = InfoMessage.getInfoMessageById(207).textId
            if textId == 773221:  # Can't join when in state invulnerable
                if self.JoinFightRequestTimer:
                    self.JoinFightRequestTimer.cancel()
                    self.JoinFightRequestTimer = None
                self.joinFight(self.joiningFightId)
            return False
        
    def askMembersToFollowTransit(self, transition: Transition, dstMapId):
        for follower in self.followers:
            self.rpcFrame.askFollowTransition(follower.login, transition, dstMapId)

    def askMembersToMoveToVertex(self, vertex: Vertex):
        for follower in self.followers:
            self.rpcFrame.askMoveToVertex(follower.login, vertex)

    def requestMapData(self):
        mirmsg = MapInformationsRequestMessage()
        mirmsg.init(mapId_=MapDisplayManager().currentMapPoint.mapId)
        ConnectionsHandler().send(mirmsg)
