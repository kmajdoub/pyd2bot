import json
import threading

from pyd2bot.logic.common.frames.BotRPCFrame import BotRPCFrame
from pyd2bot.thriftServer.pyd2botService.ttypes import Character
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager, KernelEvts
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from time import sleep
from typing import TYPE_CHECKING, Tuple
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
from pydofus2.com.ankamagames.dofus.network.messages.game.chat.ChatClientPrivateMessage import ChatClientPrivateMessage
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
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority
from pyd2bot.apis.MoveAPI import MoveAPI
from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.logic.roleplay.frames.BotAutoTripFrame import BotAutoTripFrame
from pyd2bot.logic.roleplay.messages.AutoTripEndedMessage import AutoTripEndedMessage
from pyd2bot.misc.BotEventsmanager import BotEventsManager

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayEntitiesFrame import RoleplayEntitiesFrame
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayMovementFrame import RoleplayMovementFrame
    from pyd2bot.logic.roleplay.frames.BotFarmPathFrame import BotFarmPathFrame
    from thrift.transport.TTransport import TBufferedTransport
    from pyd2bot.thriftServer.pyd2botService.Pyd2botService import Client as Pyd2botServiceClient

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
        for follower in self.followers:
            self.fetchFollowerStatus(follower)
            
    def fetchFollowerStatus(self, follower: Character):
        Logger().debug(f"[BotPartyFrame] Fetching follower {follower.login} status")
        return self.rpcFrame.askForStatus(follower.login, lambda result, error:self.onFollowerStatus(follower, result, error))
    
    def onFollowerStatus(self, follower: Character, status: str, error: str):
        Logger().debug(f"[BotPartyFrame] Follower {follower.login} status: {status}")
        if error is not None:
            raise Exception(f"Error while fetching follower status: {error}")
        self._followerStatus[follower.login] = status
        if all(status is not None for status in self._followerStatus.values()):
            if all(status == "idle" for status in self._followerStatus.values()):
                if self._fetchStatusTimer:
                    self._fetchStatusTimer.cancel()
                BotEventsManager().send(BotEventsManager.ALL_PARTY_MEMBERS_IDLE)
            else:
                Logger().info(f"Not all members idle, statuses: {self._followerStatus}")
                self._followerStatus = {follower.login: None for follower in self.followers}
                self._fetchStatusTimer = BenchmarkTimer(3, self.checkAllMembersIdle)
                self._fetchStatusTimer.start()

    def pulled(self):
        if self.currentPartyId:
            self.leaveParty()
        self.partyMembers.clear()
        if self.partyInviteTimers:
            for timer in self.partyInviteTimers.values():
                timer.cancel()
        self.currentPartyId = None
        self.partyInviteTimers.clear()
        return True

    def pushed(self):
        self.partyInviteTimers = dict[str, BenchmarkTimer]()
        self.currentPartyId = None
        self.partyMembers = dict[int, PartyMemberInformations]()
        self.joiningLeaderVertex: Vertex = None
        self._wantsToJoinFight = None
        self.followingLeaderTransition = None
        self._followerStatus = { follower.login: None for follower in self.followers}
        self._fetchStatusTimer = None
        if self.isLeader:
            self.init()
        return True

    def init(self):
        if WorldPathFinder().currPlayerVertex is None:
            Logger().debug("[BotPartyFrame] Cant invite members before am in game")
            KernelEventsManager().once(KernelEvts.MAPPROCESSED, lambda e:self.init())
            return
        Logger().debug(f"[BotPartyFrame] Send party invite to all followers.")
        for follower in self.followers:
            Logger().debug(f"[BotPartyFrame] Will Send party invite to {follower.name}")
            self.sendPartyInvite(follower.name)

    def getFollowerById(self, id: int) -> dict:
        for follower in self.followers:
            if follower.id == id:
                return follower
        return None

    def getFollowerByName(self, name: str) -> dict:
        for follower in self.followers:
            if follower.name == name:
                return follower
        return None

    def sendPrivateMessage(self, playerName, message):
        ccmsg = ChatClientPrivateMessage()
        pi = PlayerSearchCharacterNameInformation()
        pi.init(playerName)
        ccmsg.init(pi, message)
        ConnectionsHandler().conn.send(ccmsg)

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
        Logger().debug(f"[BotPartyFrame] Send follow member {memberId}")
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
            Logger().debug(f"[BotPartyFrame] {msg.leavingPlayerId} left the party")
            player = self.partyMembers.get(msg.leavingPlayerId)
            if player:
                del self.partyMembers[msg.leavingPlayerId]
            if self.isLeader:
                follower = self.getFollowerById(msg.leavingPlayerId)
                self.sendPartyInvite(follower.name)
            return True

        elif isinstance(msg, PartyDeletedMessage):
            self.currentPartyId = None
            self.partyMembers.clear()
            if self.isLeader:
                for follower in self.followers:
                    self.sendPartyInvite(follower.name)
            return True

        elif isinstance(msg, PartyInvitationMessage):
            Logger().debug(f"[BotPartyFrame] {msg.fromName} invited you to join his party.")
            if not self.isLeader and int(msg.fromId) == int(self.leader.id):
                paimsg = PartyAcceptInvitationMessage()
                paimsg.init(msg.partyId)
                ConnectionsHandler().conn.send(paimsg)
                Logger().debug(f"[BotPartyFrame] Accepted party invite from {msg.fromName}.")
            else:
                pirmsg = PartyRefuseInvitationMessage()
                pirmsg.init(msg.partyId)
                ConnectionsHandler().conn.send(pirmsg)
            return True

        elif isinstance(msg, PartyNewMemberMessage):
            member = msg.memberInformations
            Logger().info(f"[BotPartyFrame] '{member.name}' joined your party")
            self.currentPartyId = msg.partyId
            self.partyMembers[member.id] = member
            if member.id != PlayedCharacterManager().id:
                if self.isLeader:
                    self.sendFollowMember(member.id)
                    if member.name in self.partyInviteTimers:
                        self.partyInviteTimers[member.name].cancel()
                        del self.partyInviteTimers[member.name]
                        if not self.partyInviteTimers:
                            self.onAllMembersJoinedParty()
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

        elif isinstance(msg, LeaderTransitionMessage):
            if msg.transition.transitionMapId == PlayedCharacterManager().currentMap.mapId:
                Logger().warning(
                    f"[BotPartyFrame] Leader '{self.leader.name}' is heading to my current map '{msg.transition.transitionMapId}', nothing to do."
                )
            else:
                Logger().debug(f"[BotPartyFrame] Will follow '{self.leader.name}' transit '{msg.transition}'")
                self.followingLeaderTransition = msg.transition
                MoveAPI.followTransition(msg.transition)
            return True

        elif isinstance(msg, LeaderPosMessage):
            self.leaderCurrVertex = msg.vertex
            if self.joiningLeaderVertex is not None:
                if msg.vertex.UID == self.joiningLeaderVertex.UID:
                    return True
                else:
                    Logger().warning(
                        f"[BotPartyFrame] Received another leader pos {msg.vertex} while still following leader pos {self.joiningLeaderVertex}."
                    )
                    return True
            elif (
                WorldPathFinder().currPlayerVertex is not None
                and WorldPathFinder().currPlayerVertex.UID != msg.vertex.UID
            ):
                Logger().debug(f"[BotPartyFrame] Leader {self.leaderName} is in vertex {msg.vertex}, will follow it.")
                self.joiningLeaderVertex = msg.vertex
                af = BotAutoTripFrame(msg.vertex.mapId, msg.vertex.zoneId)
                Kernel().worker.pushFrame(af)
                return True
            else:
                Logger().debug(f"[BotPartyFrame] Player is already in leader vertex {msg.vertex}")
                return True

        elif isinstance(msg, CompassUpdatePartyMemberMessage):
            if msg.memberId in self.partyMembers:
                self.partyMembers[msg.memberId].worldX = msg.coords.worldX
                self.partyMembers[msg.memberId].worldY = msg.coords.worldY
                Logger().debug(
                    f"[BotPartyFrame] Member {msg.memberId} moved to map {(msg.coords.worldX, msg.coords.worldY)}"
                )
                return True
            else:
                Logger().warning(f"[BotPartyFrame] Seems ig we are in party but not modeled yet in party frame")

        elif isinstance(msg, MapComplementaryInformationsDataMessage):
            if not self.isLeader:
                Logger().debug(
                    f"*********************************** New map {msg.mapId} **********************************************"
                )
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

    def setFollowLeader(self):
        if not self.isLeader:
            if not self.movementFrame:
                KernelEventsManager().onFramePush("RoleplayMovementFrame", self.setFollowLeader)
                return
            self.movementFrame.setFollowingActor(self.leader.id)

    def notifyFollowerWithPos(self, follower: Character):
        cv = WorldPathFinder().currPlayerVertex
        if cv is None:
            KernelEventsManager().once(KernelEvts.MAPPROCESSED, lambda e: self.notifyFollowerWithPos(follower))
            return
        self.rpcFrame.askMoveToVertex(follower.login, cv)

    def notifyFollowersWithTransition(self, tr: Transition):
        for follower in self.followers:
            self.notifyFollowerWithTransition(follower, tr)

    def notifyFollowerWithTransition(self, follower: Character, tr: Transition):
        self.rpcFrame.askFollowTransition(follower.login, tr)

    def notifyFollowesrWithPos(self):
        for follower in self.followers:
            self.notifyFollowerWithPos(follower)

    def requestMapData(self):
        mirmsg = MapInformationsRequestMessage()
        mirmsg.init(mapId_=MapDisplayManager().currentMapPoint.mapId)
        ConnectionsHandler().conn.send(mirmsg)

    def moveToVertex(self, vertex: Vertex):
        Logger().debug(f"[BotPartyFrame] Moving to vertex {vertex}")
        self.joiningLeaderVertex = vertex
        af = BotAutoTripFrame(vertex.mapId, vertex.zoneId)
        Kernel().worker.pushFrame(af)
        return True

    def onAllMembersJoinedParty(self):
        self.notifyFollowesrWithPos()