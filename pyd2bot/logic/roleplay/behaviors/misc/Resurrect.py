from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.enums.PlayerLifeStatusEnum import \
    PlayerLifeStatusEnum
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.death.GameRolePlayFreeSoulRequestMessage import \
    GameRolePlayFreeSoulRequestMessage
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import \
    BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class Resurrect(AbstractBehavior):
    CEMETERY_MAP_LOADED_TIMEOUT = 7
    
    def __init__(self) -> None:
        super().__init__()
        self.requestTimer = None
        self.cemeteryMapLoadedListener = None

    def run(self) -> bool:
        self.phenixMapId = Kernel().playedCharacterUpdatesFrame._phenixMapId
        if not PlayedCharacterManager().currentMap:
            return self.once_map_rendered(self.start)
        self.on(KernelEvent.PlayerStateChanged, self.onPlayerStateChange)
        if PlayedCharacterManager().player_life_status == PlayerLifeStatusEnum.STATUS_PHANTOM:
            Logger().debug(f"Traveling to phenix map {self.phenixMapId}")
            self.autoTrip(dstMapId=self.phenixMapId, callback=self.onPhenixMapReached)
        elif PlayedCharacterManager().player_life_status == PlayerLifeStatusEnum.STATUS_TOMBSTONE:
            self.cemeteryMapLoadedListener = self.once_map_rendered(self.onCemeteryMapLoaded)
            self.releaseSoulRequest()
        else:
            self.finish(1, f"Unknown user state {PlayedCharacterManager().player_life_status}!!")

    def onPlayerStateChange(self, event, playerState: PlayerLifeStatusEnum, phenixMapId):
        self.phenixMapId = phenixMapId
        Logger().debug(f"Phoenix mapId : {phenixMapId}")
        if playerState == PlayerLifeStatusEnum.STATUS_PHANTOM:
            Logger().info(f"Player soul released waiting for cemetery map to load.")
        elif playerState == PlayerLifeStatusEnum.STATUS_ALIVE:
            Logger().info("Player is alive and kicking.")
            self.finish(0)

    def onCemeteryMapLoaded(self, event_id=None):
        Logger().debug(f"Cemetery map loaded.")
        if self.requestTimer:
            self.requestTimer.cancel()
            
        self.autoTrip(dstMapId=self.phenixMapId, callback=self.onPhenixMapReached)

    def onPhenixSkillUsed(self, code, error, iePosition=None):
        if error:
            return self.finish(code, error)
        
        Logger().info("Phenix revive skill used")

    def onPhenixMapReached(self, code, error):
        if error:
            return self.finish(code, error)
        
        if Kernel().interactiveFrame:
            reviveIE = Kernel().interactiveFrame.getReviveIe()
            self.use_skill(ie=reviveIE, callback=self.onPhenixSkillUsed)
        else:
            self.once_frame_pushed("RoleplayInteractivesFrame", self.onPhenixMapReached)
            
    def onCemeteryMapLoadedTimeout(self):
        Logger().error("Cemetery map loaded timeout.")
        self.cemeteryMapLoadedListener.delete()
        self.autoTrip(dstMapId=self.phenixMapId, callback=self.onPhenixMapReached)
            
    def releaseSoulRequest(self):
        self.requestTimer = BenchmarkTimer(self.CEMETERY_MAP_LOADED_TIMEOUT, self.onCemeteryMapLoadedTimeout)
        self.requestTimer.start()
        ConnectionsHandler().send(GameRolePlayFreeSoulRequestMessage())
