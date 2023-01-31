from pyd2bot.logic.managers.BotConfig import BotConfig
from build.lib.pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEvts
from pydofus2.com.ankamagames.berilia.managers.EventsHandler import EventsHandler
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.GameRolePlayActorInformations import GameRolePlayActorInformations
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
        def onEvt(e, infos: GameRolePlayActorInformations):
            entitiesFrame: "RoleplayEntitiesFrame" = Kernel().worker.getFrame("RoleplayEntitiesFrame")
            if entitiesFrame is None:
                KernelEventsManager().onceFramePushed("RoleplayEntitiesFrame", onEvt, [e, infos])
            for follower in BotConfig().followers:
                if not entitiesFrame.getEntityInfos(follower.id):
                    self.oncePartyMemberShowed(onEvt)
                    return
            Logger().info("All party members showed")
            callback(*args)
        self.oncePartyMemberShowed(onEvt)
    
    def onAllPartyMembersIdle(self, callback, args=[]):
        def onEvt(e):
            callback(*args)
        self.once(BotEventsManager.ALL_PARTY_MEMBERS_IDLE, onEvt)
        
    def oncePartyMemberShowed(self, callback, args=[]):
        def onEvt(e, infos: GameRolePlayActorInformations):
            for follower in BotConfig().followers:
                if int(follower.id) == int(infos.contextualId):
                    callback(*args)
        KernelEventsManager().once(KernelEvts.ACTORSHOWED, onEvt)