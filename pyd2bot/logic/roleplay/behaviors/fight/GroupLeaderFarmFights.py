from typing import TYPE_CHECKING
from pyd2bot.logic.roleplay.behaviors.fight.SoloFarmFights import SoloFarmFights
from pyd2bot.logic.roleplay.behaviors.party.WaitForMembersToShow import \
    WaitForMembersToShow
from pyd2bot.logic.roleplay.messages.FollowTransitionMessage import \
    FollowTransitionMessage
from pyd2bot.logic.roleplay.messages.MoveToVertexMessage import \
    MoveToVertexMessage
from pyd2bot.farmPaths.AbstractFarmPath import AbstractFarmPath
from pyd2bot.data.models import Character
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.TransitionTypeEnum import \
    TransitionTypeEnum
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

if TYPE_CHECKING:
    pass

class GroupLeaderFarmFights(SoloFarmFights):

    def __init__(self, path: AbstractFarmPath, fightsPerMinute: int, fightPartyMembers: list[Character], monsterLvlCoefDiff=None, followers: list[Character]=None, timeout=None):
        super().__init__(path, fightsPerMinute, fightPartyMembers, monsterLvlCoefDiff, timeout)
        self.followers = followers

    def moveToNextStep(self):
        super().moveToNextStep()
        self.askFollowersMoveToVertex(self._currEdge.dst)

    def makeAction(self):
        if self.followers:
            Logger().info("Waiting for party members to be idle.")
            self.waitForMembersIdle(self.followers, callback=self.onMembersIdle)
            return False
        super().makeAction()

    def onMembersIdle(self, code, err):
        if err:
            return KernelEventsManager().send(KernelEvent.ClientRestart, f"Wait members idle failed for reason : {err}")
        if not self.allMembersOnSameMap():
            Logger().warning("Followers are not all on the same map!")
            self.askFollowersMoveToVertex(self.path.currentVertex)
            self.waitForMembersToShow(self.followers, callback=self.onMembersShowed)
            return False
        super().makeAction()

    def onMembersShowed(self, code, err):
        if err:
            if code == WaitForMembersToShow.MEMBER_DISCONNECTED:
                Logger().warning(f"Member {err} disconnected while waiting for them to show up")
            else:
                KernelEventsManager().send(KernelEvent.ClientRestart, f"Error while waiting for members to show up: {err}")
                return False
        Logger().warning("Followers are all on same map")
        self.makeAction()
 
    def askMembersFollow(self, transition: TransitionTypeEnum, dstMapId):
        for follower in self.followers:
            Kernel.getInstance(follower.accountId).worker.process(FollowTransitionMessage(transition, dstMapId))

    def askFollowersMoveToVertex(self, vertex: Vertex):
        for follower in self.followers:
            entity = Kernel().roleplayEntitiesFrame.getEntityInfos(follower.id)
            if not entity:
                Kernel.getInstance(follower.accountId).worker.process(MoveToVertexMessage(vertex))                
                Logger().debug(f"Asked follower {follower.accountId} to go to farm start vertex")
            
    def allMembersOnSameMap(self):
        for follower in self.followers:
            if Kernel().roleplayEntitiesFrame is None:
                return False
            entity = Kernel().roleplayEntitiesFrame.getEntityInfos(follower.id)
            if not entity:
                return False
        return True
