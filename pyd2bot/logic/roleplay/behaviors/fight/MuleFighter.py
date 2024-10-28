from time import perf_counter

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.movement.MapMove import MapMove
from pyd2bot.misc.BotEventsManager import BotEventsManager
from pyd2bot.data.models import Character
from pydofus2.com.ankamagames.berilia.managers.EventsHandler import (Event,
                                                                     Listener)
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import \
    Vertex
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightJoinRequestMessage import \
    GameFightJoinRequestMessage
from pydofus2.com.ankamagames.dofus.network.types.game.context.fight.FightCommonInformations import \
    FightCommonInformations
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint


class MuleFighter(AbstractBehavior):
    FIGHT_JOIN_TIMEOUT = 3

    def __init__(self, leader: Character):
        super().__init__()
        self.joinFightListener = None
        self.leader = leader
    
    def run(self):
        self.on(KernelEvent.FightSwordShowed, self.onFightStarted)
        self.on(KernelEvent.ServerTextInfo, self.onServerNotif)
        self.on(KernelEvent.FightEnded, self.onFightEnd)
        BotEventsManager().on(BotEventsManager.MOVE_TO_VERTEX, self.onMoveToVertex, originator=self)
        self.checkPlayerState()
    
    def onRevived(self, code, error, callback=None):
        if error:
            KernelEventsManager().send(KernelEvent.ClientShutdown, f"Error[{code}] while auto-reviving player: {error}")
            return 
        Logger().debug(f"Bot back on form, can continue mule fighting!")
        if callback is not None:
            callback()

    def onFightEnd(self, event):
        Logger().debug("Fight ended, waiting for roleplay to start before checking status")
        self.once(KernelEvent.RoleplayStarted, lambda e: self.onceMapProcessed(self.checkPlayerState))

    def checkPlayerState(self):
        if PlayedCharacterManager().isDead():
            Logger().warning("Mule is dead, we need to revive it!")
            self.autoRevive(callback=lambda code, err: self.onRevived(code, err))

    def onMoveToVertex(self, event: Event, vertex: Vertex):
        Logger().info(f"Move to vertex {vertex} received")
        if PlayedCharacterManager().isDead():
            Logger().warning(f"Player is dead need to revive it first.")
            return self.autoRevive(callback=lambda code, err: self.onRevived(code, err))
        
        for behavior in self.getOtherRunningBehaviors():
            if not behavior.IS_BACKGROUND_TASK:
                Logger().warning(f"I have other non background tasks running {self.getOtherRunningBehaviors()}, can't move to vertex.")
                return behavior.onFinish(lambda: self.onMoveToVertex(event, vertex))

        if PlayedCharacterManager().currVertex is not None:
            if PlayedCharacterManager().currVertex.UID != vertex.UID:
                self.travelUsingZaap(vertex.mapId, vertex.zoneId, callback=self.onDestVertexTrip)
            else:
                Logger().info("Dest vertex is the same as the current player vertex")
        else:
            Logger().error("Can't move with unknown player vertex")
            self.onceMapProcessed(lambda: self.onMoveToVertex(event, vertex))

    def onDestVertexTrip(self, code, error):
        if error:
            Logger().error(f"Error while trying to move to destination vertex : {error}")

    def onServerNotif(self, event, msgId, msgType, textId, text, params):
        if textId == 773221:
            self.joinFightListener.delete()
            secondsToWait = int(params[0])
            startTime = perf_counter()
            Logger().info(f"Need to wail {secondsToWait}s before i can join leader fight")
            currentMPChilds = MapPoint.fromCellId(PlayedCharacterManager().currentCellId).iterChildren(False)
            try:
                x, y = next(currentMPChilds)
            except StopIteration:
                remaining = secondsToWait - (perf_counter() - startTime)
                if remaining > 0:
                    Kernel().worker.terminated.wait(secondsToWait)
                return self.joinFight()
            def onMoved(code, err, landingCell):
                if err:
                    try:    
                        x, y = next(currentMPChilds)
                    except StopIteration:
                        remaining = secondsToWait - (perf_counter() - startTime)
                        if remaining > 0:
                            Kernel().worker.terminated.wait(secondsToWait)
                        return self.joinFight()
                    return MapMove().start(MapPoint.fromCoords(x, y).cellId, callback=onMoved, parent=self)
                self.joinFight()
            self.mapMove(MapPoint.fromCoords(x, y).cellId, callback=onMoved)
                
    def onFightStarted(self, event: Event, infos: FightCommonInformations):
        for team in infos.fightTeams:
            if team.leaderId == self.leader.id:
                Logger().debug("Leader started a fight!")
                self.fightId = infos.fightId
                return self.joinFight()
    
    def onFight(self, event) -> None:
        Logger().info("Leader fight joined successfully")

    def onJoinFightTimeout(self, listener: Listener) -> None:
        Logger().warning("Join fight request timeout")
        listener.armTimer()
        self.sendJoinFightRequest()
    
    def joinFight(self):
        self.joinFightListener = KernelEventsManager().once(
            KernelEvent.FightStarted, 
            self.onFight, 
            timeout=self.FIGHT_JOIN_TIMEOUT, 
            ontimeout=self.onJoinFightTimeout, 
            originator=self
        )
        self.sendJoinFightRequest()

    def sendJoinFightRequest(self):
        gfjrmsg = GameFightJoinRequestMessage()
        gfjrmsg.init(self.leader.id, self.fightId)
        ConnectionsHandler().send(gfjrmsg)
    
    def stop(self):
        self.finish(True, None)
