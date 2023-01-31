from pyd2bot.logic.managers.BotConfig import BotConfig
from pydofus2.com.ankamagames.berilia.managers.EventsHandler import EventsHandler
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager, KernelEvts
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.GameRolePlayActorInformations import (
    GameRolePlayActorInformations,
)
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.metaclasses.Singleton import Singleton

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayEntitiesFrame import RoleplayEntitiesFrame


class BotEventsManager(EventsHandler, metaclass=Singleton):
    MEMBERS_READY = 0
    ALL_PARTY_MEMBERS_IDLE = 1

    def __init__(self):
        super().__init__()

    def onAllPartyMembersShowed(self, callback, args=[]):
        def onTeamMemberShowed(e, infos: GameRolePlayActorInformations):
            entitiesFrame: "RoleplayEntitiesFrame" = Kernel().worker.getFrame("RoleplayEntitiesFrame")
            if entitiesFrame is None:
                Logger().info("Waiting for RoleplayEntitiesFrame to show up")
                KernelEventsManager().onceFramePushed("RoleplayEntitiesFrame", onTeamMemberShowed, [e, infos])
            notShowed = []
            for follower in BotConfig().followers:
                if not entitiesFrame.getEntityInfos(follower.id):
                    notShowed.append(follower.name)
            if len(notShowed) > 0:
                Logger().info(f"Waiting for party members {notShowed} to show up!")
                return
            Logger().info("All party members showed!")
            KernelEventsManager().remove_listener(KernelEvts.ACTORSHOWED, onActorShowed)
            KernelEventsManager().remove_listener(KernelEvts.ACTORSHOWED, onTeamMemberShowed)
            callback(*args)

        def onActorShowed(e, infos: GameRolePlayActorInformations):
            for follower in BotConfig().followers:
                if int(follower.id) == int(infos.contextualId):
                    Logger().info(f"Party member {follower.name} showed")
                    onTeamMemberShowed(e, infos)

        KernelEventsManager().on(KernelEvts.ACTORSHOWED, onActorShowed)

    def onAllPartyMembersIdle(self, callback, args=[]):
        def onEvt(e):
            callback(*args)

        self.once(BotEventsManager.ALL_PARTY_MEMBERS_IDLE, onEvt)

    def oncePartyMemberShowed(self, callback, args=[]):
        def onActorShowed(e, infos: GameRolePlayActorInformations):
            Logger().info("Actor showed %s" % infos.contextualId)
            for follower in BotConfig().followers:
                if int(follower.id) == int(infos.contextualId):
                    Logger().info("Party member %s showed" % follower.name)
                    callback(*args)

        KernelEventsManager().on(KernelEvts.ACTORSHOWED, onActorShowed)
