from time import sleep
from pyd2bot.logic.common.frames.BotRPCFrame import BotRPCFrame
from pyd2bot.thriftServer.pyd2botService.ttypes import Character
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager, KernelEvent
from pydofus2.com.ankamagames.dofus.network.enums.PartyJoinErrorEnum import PartyJoinErrorEnum
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyCannotJoinErrorMessage import PartyCannotJoinErrorMessage
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Transition import Transition
from pyd2bot.logic.roleplay.messages.LeaderPosMessage import LeaderPosMessage
from pyd2bot.logic.roleplay.messages.LeaderTransitionMessage import LeaderTransitionMessage
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import MapDisplayManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldPathFinder import WorldPathFinder
from pydofus2.com.ankamagames.dofus.network.messages.game.atlas.compass.CompassUpdatePartyMemberMessage import (
    CompassUpdatePartyMemberMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapChangeFailedMessage import (
    MapChangeFailedMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapComplementaryInformationsDataMessage import (
    MapComplementaryInformationsDataMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapInformationsRequestMessage import (
    MapInformationsRequestMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyAcceptInvitationMessage import (
    PartyAcceptInvitationMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyCancelInvitationMessage import (
    PartyCancelInvitationMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyDeletedMessage import (
    PartyDeletedMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyFollowMemberRequestMessage import (
    PartyFollowMemberRequestMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyInvitationMessage import (
    PartyInvitationMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyInvitationRequestMessage import (
    PartyInvitationRequestMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyJoinMessage import (
    PartyJoinMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyLeaveRequestMessage import (
    PartyLeaveRequestMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyMemberInStandardFightMessage import (
    PartyMemberInStandardFightMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyMemberRemoveMessage import (
    PartyMemberRemoveMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyNewGuestMessage import (
    PartyNewGuestMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyNewMemberMessage import (
    PartyNewMemberMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyRefuseInvitationMessage import (
    PartyRefuseInvitationMessage,
)
from pydofus2.com.ankamagames.dofus.network.types.common.PlayerSearchCharacterNameInformation import (
    PlayerSearchCharacterNameInformation,
)
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.party.PartyMemberInformations import (
    PartyMemberInformations,
)
from pydofus2.com.ankamagames.jerakine.data.I18n import I18n
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority
from pyd2bot.apis.MoveAPI import MoveAPI
from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.logic.roleplay.frames.BotAutoTripFrame import BotAutoTripFrame
from pyd2bot.logic.roleplay.messages.AutoTripEndedMessage import AutoTripEndedMessage
from pyd2bot.misc.BotEventsmanager import BotEventsManager
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayEntitiesFrame import RoleplayEntitiesFrame
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayMovementFrame import RoleplayMovementFrame
    from pyd2bot.logic.roleplay.frames.BotFarmPathFrame import BotFarmPathFrame


class BotPartyFrame(Frame):
    ASK_INVITE_TIMOUT = 10
    CONFIRME_JOIN_TIMEOUT = 5

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
        return Kernel().worker.getFrame("RoleplayMovementFrame")

    @property
    def entitiesFrame(self) -> "RoleplayEntitiesFrame":
        return Kernel().worker.getFrame("RoleplayEntitiesFrame")

    @property
    def farmFrame(self) -> "BotFarmPathFrame":
        return Kernel().worker.getFrame("BotFarmPathFrame")

    @property
    def rpcFrame(self) -> "BotRPCFrame":
        return Kernel().worker.getFrame("BotRPCFrame")

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
            nonIdleMemberNames = [name for name, status in self._followerStatus.items() if status != "idle"]
            if nonIdleMemberNames:
                Logger().info(f"[BotPartyFrame] Waiting for members {nonIdleMemberNames}.")
                sleep(1)
                self.checkAllMembersIdle()
            else:
                Logger().info(f"[BotPartyFrame] All members are idle.")
                self.allMembersIdle = False
                BotEventsManager().send(BotEventsManager.ALL_PARTY_MEMBERS_IDLE)

    def pulled(self):
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
        self._wantsToJoinFight = None
        self.followingLeaderTransition = None
        self._followerStatus = {follower.login: None for follower in self.followers}
        if self.isLeader:
            KernelEventsManager().once(KernelEvent.MAPPROCESSED, lambda e: self.inviteAllFollowers())
        return True

    def inviteAllFollowers(self):
        for follower in self.followers:
            self.sendPartyInvite(follower.name)

    def getPartyMemberById(self, id: int) -> Character:
        for follower in self.followers:
            if int(follower.id) == int(id):
                return follower
        if id == self.leader.id:
            return self.leader
        return None

    def getFollowerByName(self, name: str) -> dict:
        for follower in self.followers:
            if follower.name == name:
                return follower
        return None

    def cancelPartyInvite(self, playerName):
        follower = self.getFollowerByName(playerName)
        if follower and self.currentPartyId is not None:
            cpimsg = PartyCancelInvitationMessage()
            cpimsg.init(follower.id, self.currentPartyId)
            ConnectionsHandler().conn.send(cpimsg)
            return True
        return False

    def sendPartyInvite(self, playerName):
        if self.partyInviteTimers.get(playerName):
            self.partyInviteTimers[playerName].cancel()
            self.cancelPartyInvite(playerName)
        follower = self.getFollowerByName(playerName)
        if follower.id not in self.partyMembers:
            pimsg = PartyInvitationRequestMessage()
            pscni = PlayerSearchCharacterNameInformation()
            pscni.init(playerName)
            pimsg.init(pscni)
            ConnectionsHandler().conn.send(pimsg)
            self.partyInviteTimers[playerName] = BenchmarkTimer(
                self.CONFIRME_JOIN_TIMEOUT, self.sendPartyInvite, [playerName]
            )
            self.partyInviteTimers[playerName].start()
            Logger().debug(f"[BotPartyFrame] Join party invitation sent to {playerName}")

    def sendFollowMember(self, memberId):
        pfmrm = PartyFollowMemberRequestMessage()
        pfmrm.init(memberId, self.currentPartyId)
        ConnectionsHandler().conn.send(pfmrm)

    def joinFight(self, fightId: int):
        if self.movementFrame._isMoving:
            self.movementFrame._wantsToJoinFight = {
                "fightId": fightId,
                "fighterId": self.leader.id,
            }
        else:
            self.movementFrame.joinFight(self.leader.id, fightId)

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
        plmsg = PartyLeaveRequestMessage()
        plmsg.init(self.currentPartyId)
        ConnectionsHandler().conn.send(plmsg)
        self.currentPartyId = None

    def process(self, msg: Message):

        if isinstance(msg, PartyNewGuestMessage):
            return True

        elif isinstance(msg, MapChangeFailedMessage):
            Logger().error(f"[BotPartyFrame] received map change failed for reason: {msg.reason}")

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
            notifText = I18n.getUiText("ui.common.invitation") + " " + I18n.getUiText("ui.party.playerInvitation", [f"player,{msg.fromId}::{msg.fromName}"])
            Logger().debug(f"[BotPartyFrame] {notifText}.")
            if not self.isLeader and int(msg.fromId) == int(self.leader.id):
                paimsg = PartyAcceptInvitationMessage()
                paimsg.init(msg.partyId)
                ConnectionsHandler().conn.send(paimsg)
                Logger().debug(f"[BotPartyFrame] Accepted party invite from '{msg.fromName}'.")
            else:
                pirmsg = PartyRefuseInvitationMessage()
                pirmsg.init(msg.partyId)
                ConnectionsHandler().conn.send(pirmsg)
            return True

        elif isinstance(msg, PartyNewMemberMessage):
            member = msg.memberInformations
            Logger().info(f"[BotPartyFrame] '{member.name}' joined your party.")
            self.currentPartyId = msg.partyId
            self.partyMembers[member.id] = member
            if member.id != PlayedCharacterManager().id:
                if self.isLeader:
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
            membersNotInParty = [follower for follower in self.followers if follower.id not in self.partyMembers]
            if not membersNotInParty:
                self.allMembersJoinedParty = True
                BotEventsManager().send(BotEventsManager.ALL_MEMBERS_JOINED_PARTY)
            else:
                self.allMembersJoinedParty = False
                for follower in membersNotInParty:
                    self.sendPartyInvite(follower.name)
            self.checkIfTeamInFight()
            if not self.isLeader and self.leader.id not in self.partyMembers:
                self.leaveParty()
            return True

        elif isinstance(msg, AutoTripEndedMessage):
            self.joiningLeaderVertex = None
            if self.joiningLeaderVertex is not None:
                Logger().debug(f"[BotPartyFrame] AutoTrip to join party leader vertex ended.")
                leaderInfos = self.entitiesFrame.getEntityInfos(self.leader.id)
                if not leaderInfos:
                    Logger().warning(
                        f"[BotPartyFrame] Autotrip ended, was following leader transition {self.joiningLeaderVertex} but the leader {self.leaderName} is not in the current Map!"
                    )
                else:
                    self.leaderCurrVertex = self.joiningLeaderVertex
            if self._wantsToJoinFight:
                self.joinFight(self._wantsToJoinFight)
            return False

        elif isinstance(msg, LeaderTransitionMessage):
            if msg.transition.transitionMapId == PlayedCharacterManager().currentMap.mapId:
                Logger().warning(
                    f"[BotPartyFrame] Leader '{self.leader.name}' is heading to my current map '{msg.transition.transitionMapId}', nothing to do."
                )
            else:
                Logger().debug(f"[BotPartyFrame] Will follow '{self.leader.name}'")
                self.followingLeaderTransition = msg.transition
                MoveAPI.followTransition(msg.transition)
            return True

        elif isinstance(msg, LeaderPosMessage):
            self.leaderCurrVertex = msg.vertex
            if self.joiningLeaderVertex is not None:
                if msg.vertex.UID != self.joiningLeaderVertex.UID:
                    Logger().error(
                        f"[BotPartyFrame] Received another leader pos {msg.vertex} while still following leader pos {self.joiningLeaderVertex}."
                    )
            elif (
                WorldPathFinder().currPlayerVertex is not None
                and WorldPathFinder().currPlayerVertex.UID != msg.vertex.UID
            ):
                Logger().debug(f"[BotPartyFrame] Leader {self.leaderName} is in vertex {msg.vertex}, will follow it.")
                self.joiningLeaderVertex = msg.vertex
                af = BotAutoTripFrame(msg.vertex.mapId, msg.vertex.zoneId)
                Kernel().worker.pushFrame(af)
            return True

        elif isinstance(msg, CompassUpdatePartyMemberMessage):
            if msg.memberId in self.partyMembers:
                self.partyMembers[msg.memberId].worldX = msg.coords.worldX
                self.partyMembers[msg.memberId].worldY = msg.coords.worldY
            else:
                Logger().warning(f"[BotPartyFrame] Seems ig we are in party but not modeled yet in party frame")
            return True

        elif isinstance(msg, MapComplementaryInformationsDataMessage):
            if not self.isLeader:
                self.followingLeaderTransition = None

        elif isinstance(msg, PartyMemberInStandardFightMessage):
            if float(msg.memberId) == float(self.leader.id):
                Logger().debug(f"[BotPartyFrame] member {msg.memberId} started fight {msg.fightId}")
                if float(msg.fightMap.mapId) != float(PlayedCharacterManager().currentMap.mapId):
                    af = BotAutoTripFrame(msg.fightMap.mapId)
                    Kernel().worker.pushFrame(af)
                    self._wantsToJoinFight = msg.fightId
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
            elif pcjenmsg.reason in (PartyJoinErrorEnum.PARTY_JOIN_ERROR_UNMET_CRITERION,
                                    PartyJoinErrorEnum.PARTY_JOIN_ERROR_PLAYER_LOYAL):
                pass
            elif pcjenmsg.reason == PartyJoinErrorEnum.PARTY_JOIN_ERROR_PLAYER_TOO_SOLLICITED:
                reasonText = I18n.getUiText("ui.party.playerTooSollicited")
            elif pcjenmsg.reason == PartyJoinErrorEnum.PARTY_JOIN_ERROR_UNMODIFIABLE:
                reasonText = I18n.getUiText("ui.party.partyUnmodifiable")
            elif pcjenmsg.reason == PartyJoinErrorEnum.PARTY_JOIN_ERROR_PLAYER_ALREADY_INVITED:
                reasonText = I18n.getUiText("ui.party.playerAlreayBeingInvited")
            elif pcjenmsg.reason == PartyJoinErrorEnum.PARTY_JOIN_ERROR_NOT_ENOUGH_ROOM:
                reasonText = I18n.getUiText("ui.party.notEnoughRoom")
            elif pcjenmsg.reason in (PartyJoinErrorEnum.PARTY_JOIN_ERROR_COMPOSITION_CHANGED,
                                    PartyJoinErrorEnum.PARTY_JOIN_ERROR_UNKNOWN):
                reasonText = I18n.getUiText("ui.party.cantInvit")
            Logger().warning(f"[BotPartyFrame] Can't join party: {reasonText}")
            return True
        
    def askMembersToFollowTransit(self, transition: Transition):
        for follower in self.followers:
            self.rpcFrame.askFollowTransition(follower.login, transition)

    def askMembersToMoveToVertex(self, vertex: Vertex):
        for follower in self.followers:
            self.rpcFrame.askMoveToVertex(follower.login, vertex)

    def requestMapData(self):
        mirmsg = MapInformationsRequestMessage()
        mirmsg.init(mapId_=MapDisplayManager().currentMapPoint.mapId)
        ConnectionsHandler().conn.send(mirmsg)

        
