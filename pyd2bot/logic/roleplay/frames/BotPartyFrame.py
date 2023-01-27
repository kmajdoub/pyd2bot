import json
import threading
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
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapChangeFailedMessage import MapChangeFailedMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapComplementaryInformationsDataMessage import (
    MapComplementaryInformationsDataMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapInformationsRequestMessage import MapInformationsRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyAcceptInvitationMessage import (
    PartyAcceptInvitationMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyCancelInvitationMessage import (
    PartyCancelInvitationMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyDeletedMessage import PartyDeletedMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyFollowMemberRequestMessage import (
    PartyFollowMemberRequestMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyInvitationMessage import (
    PartyInvitationMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyInvitationRequestMessage import (
    PartyInvitationRequestMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.party.PartyJoinMessage import PartyJoinMessage
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
from thrift.transport.TTransport import TTransportException

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayEntitiesFrame import RoleplayEntitiesFrame
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayMovementFrame import RoleplayMovementFrame
    from pyd2bot.logic.roleplay.frames.BotFarmPathFrame import BotFarmPathFrame
    from thrift.transport.TTransport import TBufferedTransport
    from pyd2bot.thriftServer.pyd2botService.Pyd2botService import Client as Pyd2botServiceClient
logger = Logger()


class MembersMonitor(threading.Thread):
    _runningMonitors = list['MembersMonitor']()
    VERBOSE = False
    def __init__(self, bpframe: "BotPartyFrame"):
        super().__init__()
        while self._runningMonitors:
            monitor = self._runningMonitors.pop()
            monitor.stopSig.set()
        self.bpframe = bpframe
        self.stopSig = threading.Event()
        self._runningMonitors.append(self)
        self.parent = threading.current_thread()
        self.name = self.parent.name
            
    def run(self) -> None:
        logger.debug("[MembersMonitor] started")
        while not self.stopSig.is_set():
            try:
                if self.bpframe.allMembersIdle:
                    if self.bpframe.allMembersOnSameMap:
                        BotEventsManager().dispatch(BotEventsManager.MEMBERS_READY)
                    elif self.bpframe.farmFrame and self.bpframe.farmFrame.isInsideFarmPath:
                        self.bpframe.notifyFollowesrWithPos()
            except Exception as e:
                logger.error(e)
            sleep(3)
        if self in MembersMonitor._runningMonitors:
            MembersMonitor._runningMonitors.remove(self)
        logger.debug("[MembersMonitor] died")

class BotPartyFrame(Frame):
    ASK_INVITE_TIMOUT = 10
    CONFIRME_JOIN_TIMEOUT = 5
    
    def __init__(self) -> None:
        self.name: str = None
        self.changingMap: bool = False
        self.followingLeaderTransition = None
        self.wantsTransition = None
        self.followersClients : dict[int, Tuple['TBufferedTransport', 'Pyd2botServiceClient']] = {}
        super().__init__()

    @property
    def isLeader(self):
        return BotConfig().isLeader

    @property
    def followers(self):
        return BotConfig().followers

    @property
    def leaderName(self):
        return BotConfig().character["name"] if self.isLeader else BotConfig().isLeader["name"]

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
    def leader(self) -> dict:
        return BotConfig().isLeader
    
    @property
    def allMembersOnSameMap(self):
        for follower in self.followers:
            if self.entitiesFrame is None:
                return False
            entity = self.entitiesFrame.getEntityInfos(follower["id"])
            if not entity:
                return False
        return True
    
    @property
    def allMembersIdle(self):
        for follower in self.followers:
            follower["status"] = self.fetchFollowerStatus(follower)
            if follower["status"] != "idle":
                logger.debug(f"[BotPartyFrame] follower '{follower['name']}' is not idle but '{follower['status']}'")
                return False
        return True
    
    def pulled(self):
        if self.currentPartyId:
            self.leaveParty()
        if self.isLeader:
            if hasattr(self, "canFarmMonitor"):
                self.canFarmMonitor.stopSig.set()
        self.partyMembers.clear()
        if self.partyInviteTimers:
            for timer in self.partyInviteTimers.values():
                timer.cancel()
        self.currentPartyId = None
        self.partyInviteTimers.clear()
        for transport, client in self.followersClients.values():
            transport.close()
        return True

    def pushed(self):
        self.partyInviteTimers = dict[str, BenchmarkTimer]()
        self.currentPartyId = None
        self.partyMembers = dict[int, PartyMemberInformations]()
        self.joiningLeaderVertex : Vertex = None
        self._wantsToJoinFight = None
        self.followingLeaderTransition = None
        if self.isLeader:
            self.init()
        return True

    def init(self):
        if WorldPathFinder().currPlayerVertex is None:
            logger.debug("[BotPartyFrame] Cant invite members before am in game")
            BenchmarkTimer(5, self.init).start()
            return
        self.canFarmMonitor = MembersMonitor(self, group=threading.current_thread().group)
        self.canFarmMonitor.start()
        logger.debug(f"[BotPartyFrame] Send party invite to all followers.")
        for follower in self.followers:
            follower["status"] = "unknown"
            self.connectFollowerClient(follower)
            logger.debug(f"[BotPartyFrame] Will Send party invite to {follower['name']}")
            self.sendPartyInvite(follower["name"])
            
    def getFollowerById(self, id: int) -> dict:
        for follower in self.followers:
            if follower["id"] == id:
                return follower
        return None 
    
    def getFollowerByName(self, name: str) -> dict:
        for follower in self.followers:
            if follower["name"] == name:
                return follower
        return None
    
    def sendPrivateMessage(self, playerName, message):
        ccmsg = ChatClientPrivateMessage()
        pi = PlayerSearchCharacterNameInformation()
        pi.init(playerName)
        ccmsg.init(pi, message)
        ConnectionsHandler()._conn.send(ccmsg)

    def cancelPartyInvite(self, playerName):
        follower = self.getFollowerByName(playerName)
        if follower and self.currentPartyId is not None:
            cpimsg = PartyCancelInvitationMessage()
            cpimsg.init(follower["id"], self.currentPartyId)
            ConnectionsHandler()._conn.send(cpimsg)
            return True
        return False

    def sendPartyInvite(self, playerName):        
        if self.partyInviteTimers.get(playerName):
            self.partyInviteTimers[playerName].cancel()
            self.cancelPartyInvite(playerName)
        follower = self.getFollowerByName(playerName)
        if follower["id"] not in self.partyMembers:
            pimsg = PartyInvitationRequestMessage()
            pscni = PlayerSearchCharacterNameInformation()
            pscni.init(playerName)
            pimsg.init(pscni)
            ConnectionsHandler()._conn.send(pimsg)
            self.partyInviteTimers[playerName] = BenchmarkTimer(self.CONFIRME_JOIN_TIMEOUT, self.sendPartyInvite, [playerName])
            self.partyInviteTimers[playerName].start()
            logger.debug(f"[BotPartyFrame] Join party invitation sent to {playerName}")

    def sendFollowMember(self, memberId):
        pfmrm = PartyFollowMemberRequestMessage()
        pfmrm.init(memberId, self.currentPartyId)
        ConnectionsHandler()._conn.send(pfmrm)

    def joinFight(self, fightId: int):
        if self.movementFrame._isMoving:
            self.movementFrame._wantsToJoinFight = {
                "fightId": fightId,
                "fighterId": self.leader['id'],
            }
        else:
            self.movementFrame.joinFight(self.leader['id'], fightId)

    def checkIfTeamInFight(self):
        if not PlayedCharacterManager().isFighting and self.entitiesFrame:
            for fightId, fight in self.entitiesFrame._fights.items():
                for team in fight.teams:
                    for member in team.teamInfos.teamMembers:
                        if member.id in self.partyMembers:
                            logger.debug(f"[BotPartyFrame] Team is in a fight")
                            self.joinFight(fightId)
                            return

    def leaveParty(self):
        if self.currentPartyId is None:
            logger.warning("[BotPartyFrame] No party to leave")
            return
        plmsg = PartyLeaveRequestMessage()
        plmsg.init(self.currentPartyId)
        ConnectionsHandler()._conn.send(plmsg)
        self.currentPartyId = None

    def process(self, msg: Message):
        
        if isinstance(msg, PartyNewGuestMessage):
            return True

        elif isinstance(msg, MapChangeFailedMessage):
            logger.error(f"[BotPartyFrame] received map change failed for reason: {msg.reason}")

        elif isinstance(msg, PartyMemberRemoveMessage):
            logger.debug(f"[BotPartyFrame] {msg.leavingPlayerId} left the party")
            player = self.partyMembers.get(msg.leavingPlayerId)
            if player:
                del self.partyMembers[msg.leavingPlayerId]
            if self.isLeader:
                follower = self.getFollowerById(msg.leavingPlayerId)
                self.sendPartyInvite(follower["name"])
            return True

        elif isinstance(msg, PartyDeletedMessage):
            self.currentPartyId = None
            self.partyMembers.clear()
            if self.isLeader:
                for follower in self.followers:
                    self.sendPartyInvite(follower["name"])
            return True

        elif isinstance(msg, PartyInvitationMessage):
            logger.debug(f"[BotPartyFrame] {msg.fromName} invited you to join his party.")
            if not self.isLeader and int(msg.fromId) == int(self.leader["id"]):
                paimsg = PartyAcceptInvitationMessage()
                paimsg.init(msg.partyId)
                ConnectionsHandler()._conn.send(paimsg)
                logger.debug(f"[BotPartyFrame] Accepted party invite from {msg.fromName}.")
            else:
                pirmsg = PartyRefuseInvitationMessage()
                pirmsg.init(msg.partyId)
                ConnectionsHandler()._conn.send(pirmsg)
            return True

        elif isinstance(msg, PartyNewMemberMessage):
            logger.info(f"[BotPartyFrame] {msg.memberInformations.name} joined your party")
            self.currentPartyId = msg.partyId
            self.partyMembers[msg.memberInformations.id] = msg.memberInformations
            if self.isLeader and msg.memberInformations.id != PlayedCharacterManager().id:
                self.sendFollowMember(msg.memberInformations.id)
                follower = self.getFollowerById(msg.memberInformations.id)
                if msg.memberInformations.name in self.partyInviteTimers:
                    self.partyInviteTimers[msg.memberInformations.name].cancel()
                    del self.partyInviteTimers[msg.memberInformations.name]
            elif msg.memberInformations.id == PlayedCharacterManager().id:
                self.sendFollowMember(self.leader['id'])
            return True
    
        elif isinstance(msg, PartyJoinMessage):
            self.partyMembers.clear()
            logger.debug(f"[BotPartyFrame] Joined Party {msg.partyId} of leader {msg.partyLeaderId}")
            if not self.isLeader and msg.partyLeaderId != self.leader["id"]:
                logger.warning(f"[BotPartyFrame] The party has the wrong leader {msg.partyLeaderId} instead of {self.leader['id']}")
                self.leaveParty()
                return
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
                            self.sendFollowMember(self.leader['id'])
            self.checkIfTeamInFight()
            if not self.isLeader and self.leader['id'] not in self.partyMembers:
                self.leaveParty()
            return True

        elif isinstance(msg, AutoTripEndedMessage):
            self.joiningLeaderVertex = None
            if self.joiningLeaderVertex is not None:
                logger.debug(f"[BotPartyFrame] AutoTrip to join party leader vertex ended.")
                leaderInfos = self.entitiesFrame.getEntityInfos(self.leader["id"])
                if not leaderInfos:
                    logger.warning(f"[BotPartyFrame] Autotrip ended, was following leader transition {self.joiningLeaderVertex} but the leader {self.leaderName} is not in the current Map!")
                else:
                    self.leader["currentVertex"] = self.joiningLeaderVertex
            if self._wantsToJoinFight:
                self.joinFight(self._wantsToJoinFight)

        elif isinstance(msg, LeaderTransitionMessage):
            if msg.transition.transitionMapId == PlayedCharacterManager().currentMap.mapId:
                logger.warning(f"[BotPartyFrame] Leader '{self.leader['name']}' is heading to my current map '{msg.transition.transitionMapId}', nothing to do.")
            else:
                logger.debug(f"[BotPartyFrame] Will follow '{self.leader['name']}' transit '{msg.transition}'")
                self.followingLeaderTransition = msg.transition
                MoveAPI.followTransition(msg.transition)
            return True
        
        elif isinstance(msg, LeaderPosMessage):
            self.leader["currentVertex"] = msg.vertex
            if self.joiningLeaderVertex is not None:
                if msg.vertex.UID == self.joiningLeaderVertex.UID:
                    return True
                else:
                    logger.warning(f"[BotPartyFrame] Received another leader pos {msg.vertex} while still following leader pos {self.joiningLeaderVertex}.")
                    return True
            elif WorldPathFinder().currPlayerVertex is not None and  WorldPathFinder().currPlayerVertex.UID != msg.vertex.UID:
                logger.debug(f"[BotPartyFrame] Leader {self.leaderName} is in vertex {msg.vertex}, will follow it.")
                self.joiningLeaderVertex = msg.vertex
                af = BotAutoTripFrame(msg.vertex.mapId, msg.vertex.zoneId)
                Kernel().worker.pushFrame(af)
                return True 
            else:
                logger.debug(f"[BotPartyFrame] Player is already in leader vertex {msg.vertex}")
                return True
            
        elif isinstance(msg, CompassUpdatePartyMemberMessage):
            if msg.memberId in self.partyMembers:
                self.partyMembers[msg.memberId].worldX = msg.coords.worldX
                self.partyMembers[msg.memberId].worldY = msg.coords.worldY
                logger.debug(f"[BotPartyFrame] Member {msg.memberId} moved to map {(msg.coords.worldX, msg.coords.worldY)}")
                return True
            else:
                logger.warning(f"[BotPartyFrame] Seems ig we are in party but not modeled yet in party frame")

        elif isinstance(msg, MapComplementaryInformationsDataMessage):
            if not self.isLeader:
                logger.debug(f"*********************************** New map {msg.mapId} **********************************************")
                self.followingLeaderTransition = None

        elif isinstance(msg, PartyMemberInStandardFightMessage):
            if float(msg.memberId) == float(self.leader['id']):
                logger.debug(f"[BotPartyFrame] member {msg.memberId} started fight {msg.fightId}")
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
                BenchmarkTimer(1, self.setFollowLeader).start()
                return
            self.movementFrame.setFollowingActor(self.leader['id'])
    
    def notifyFollowerWithPos(self, follower):
        cv = WorldPathFinder().currPlayerVertex
        if cv is None:
            BenchmarkTimer(1, self.notifyFollowerWithPos, [follower]).start()
            return
        
        transport, client = self.getFollowerClient(follower)
        if client is None:
            logger.warning(f"[BotPartyFrame] follower {follower['name']} thrift server is not connected.")
            raise Exception(f"follower {follower['name']} thrift server is not connected.")
        try:
            client.moveToVertex(json.dumps(cv.to_json()))
        except TTransportException as e:
            if e.message == "unexpected exception":
                logger.debug(f"[BotPartyFrame] follower {follower['name']} thrift server disconnected.")
                self.connectFollowerClient(follower)
                transport, client = self.getFollowerClient(follower)
                client.moveToVertex(json.dumps(cv.to_json()))     
            
    def notifyFollowersWithTransition(self, tr: Transition):
        for follower in self.followers:
            self.notifyFollowerWithTransition(follower, tr)
    
    def notifyFollowerWithTransition(self, follower: dict, tr: Transition):
        transport, client = self.getFollowerClient(follower)
        if client is None:
            logger.warning(f"[BotPartyFrame] follower '{follower['name']}' thrift server is not connected.")
            raise Exception(f"follower '{follower['name']}' thrift server is not connected.")
        try:
            client.followTransition(json.dumps(tr.to_json()))
        except TTransportException as e:
            if e.message == "unexpected exception":
                logger.debug(f"[BotPartyFrame] follower '{follower['name']}' thrift server disconnected.")
                self.connectFollowerClient(follower)
                transport, client = self.getFollowerClient(follower)
                client.followTransition(json.dumps(tr.to_json()))
                
    def notifyFollowesrWithPos(self):
        for follower in self.followers:
            self.notifyFollowerWithPos(follower)
            
    def fetchFollowerStatus(self, follower: dict):
        transport, client = self.getFollowerClient(follower)
        if client is None:
            logger.warning(f"[BotPartyFrame] follower {follower['name']} thrift server is not connected.")
            return "disconnected"
        try:
            return client.getStatus()
        except TTransportException as e:
            if e.message == "unexpected exception":
                logger.debug(f"[BotPartyFrame] follower {follower['name']} thrift server disconnected.")
                self.connectFollowerClient(follower)
                transport, client = self.getFollowerClient(follower)
                return client.getStatus()
            else:
                raise e
            
    def requestMapData(self):
        mirmsg = MapInformationsRequestMessage()
        mirmsg.init(mapId_=MapDisplayManager().currentMapPoint.mapId)
        ConnectionsHandler()._conn.send(mirmsg)

    def moveToVertex(self, vertex: Vertex):
        logger.debug(f"[BotPartyFrame] Moving to vertex {vertex}")
        self.joiningLeaderVertex = vertex
        af = BotAutoTripFrame(vertex.mapId, vertex.zoneId)
        Kernel().worker.pushFrame(af)
        return True
    
    def getFollowerClient(self, follower: dict):
        try:
            transport, client = self.followersClients[follower["id"]]
        except KeyError as e:
            return None, None
        try:
            if not transport.isOpen():
                transport.open()
        except TTransportException as e:
            if e.type == TTransportException.ALREADY_OPEN:
                pass
        return transport, client
    

    def connectFollowerClient(self, follower: dict):
        from pyd2bot import PyD2Bot

        transport, client = PyD2Bot().runClient('localhost', follower["serverPort"])
        self.followersClients[follower["id"]] = (transport, client)