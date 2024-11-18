from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.misc.BotEventsManager import BotEventsManager
from pyd2bot.data.models import Character
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.GameRolePlayHumanoidInformations import \
    GameRolePlayHumanoidInformations
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class WaitForMembersToShow(AbstractBehavior):
    MEMBER_LEFT_PARTY = 991
    MEMBER_DISCONNECTED = 997
    
    def __init__(self) -> None:
        super().__init__()

    def run(self, members: list[Character]) -> bool:
        self.members = members
        Logger().debug("Waiting for members to show up.")
        BotEventsManager().on(BotEventsManager.PLAYER_DISCONNECTED, self.onMemberDisconnected, originator=self)
        KernelEventsManager().on(KernelEvent.ActorShowed, self.onActorShowed, originator=self)

    def onTeamMemberShowed(self):
        if Kernel().roleplayEntitiesFrame is None:
            return KernelEventsManager().onceFramePushed("RoleplayEntitiesFrame", self.onTeamMemberShowed, originator=self)
        notShowed = [member.name for member in self.members if not Kernel().roleplayEntitiesFrame.getEntityInfos(member.id)]
        if len(notShowed) > 0:
            return Logger().info(f"Waiting for members {notShowed} to show up.")
        Logger().info("All party members showed.")
        self.finish(0)

    def onActorShowed(self, event, infos: "GameRolePlayHumanoidInformations"):
        Logger().info(f"Actor {infos.name} showed.")
        for member in self.members:
            if member.id == infos.contextualId:
                self.onTeamMemberShowed()

    def onMemberDisconnected(self, event, accountId, connectionType):
        for member in self.members:
            if member.accountId == accountId:
                Logger().warning(f"Member {accountId} disconnected while waiting for it to show up")
                return self.finish(self.MEMBER_DISCONNECTED, accountId)