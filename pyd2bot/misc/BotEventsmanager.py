from pyd2bot.logic.managers.BotConfig import BotConfig
from pydofus2.com.ankamagames.berilia.managers.EventsHandler import EventsHandler
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager, KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.metaclasses.Singleton import Singleton

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayEntitiesFrame import RoleplayEntitiesFrame
    from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.GameRolePlayHumanoidInformations import (
        GameRolePlayHumanoidInformations,
    )


class BotEventsManager(EventsHandler, metaclass=Singleton):
    MEMBERS_READY = 0
    ALL_PARTY_MEMBERS_IDLE = 1
    ALL_MEMBERS_JOINED_PARTY = 2

    def __init__(self):
        super().__init__()

    def onAllPartyMembersShowed(self, callback, args=[]):
        Logger().debug("[BotEventsManager] Waiting for party members to show up.")

        def onTeamMemberShowed(e, infos: "GameRolePlayHumanoidInformations"):
            entitiesFrame: "RoleplayEntitiesFrame" = Kernel().worker.getFrame("RoleplayEntitiesFrame")
            if entitiesFrame is None:
                KernelEventsManager().onceFramePushed("RoleplayEntitiesFrame", onTeamMemberShowed, [e, infos])
            notShowed = []
            for follower in BotConfig().followers:
                if not entitiesFrame.getEntityInfos(follower.id):
                    notShowed.append(follower.name)
            if len(notShowed) > 0:
                Logger().info(f"[BotEventsManager] Waiting for party members {notShowed} to show up.")
                return
            Logger().info("[BotEventsManager] All party members showed.")
            KernelEventsManager().remove_listener(KernelEvent.ACTORSHOWED, onActorShowed)
            KernelEventsManager().remove_listener(KernelEvent.ACTORSHOWED, onTeamMemberShowed)
            callback(*args)

        def onActorShowed(e, infos: "GameRolePlayHumanoidInformations"):
            Logger().info(f"[BotEventsManager] Actor {infos.name} showed.")
            for follower in BotConfig().followers:
                if int(follower.id) == int(infos.contextualId):
                    onTeamMemberShowed(e, infos)

        KernelEventsManager().on(KernelEvent.ACTORSHOWED, onActorShowed)

    def onAllPartyMembersIdle(self, callback, args=[]):
        Logger().debug("[BotEventsManager] Waiting for party members to be idle.")

        def onEvt(e):
            callback(e, *args)

        self.once(BotEventsManager.ALL_PARTY_MEMBERS_IDLE, onEvt)

    def oncePartyMemberShowed(self, callback, args=[]):
        def onActorShowed(e, infos: "GameRolePlayHumanoidInformations"):
            for follower in BotConfig().followers:
                if int(follower.id) == int(infos.contextualId):
                    Logger().info("[BotEventsManager] Party member %s showed" % follower.name)
                    callback(e, *args)

        KernelEventsManager().on(KernelEvent.ACTORSHOWED, onActorShowed)

    def onceAllMembersJoinedParty(self, callback, args=[]):
        Logger().debug("[BotEventsManager] Waiting for party members to join party.")

        def onEvt(e):
            callback(e, *args)

        self.once(BotEventsManager.ALL_MEMBERS_JOINED_PARTY, onEvt)
