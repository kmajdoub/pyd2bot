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


class AutoRevive(AbstractBehavior):
    CEMETARY_MAP_LOADED_TIMEOUT = 7
    
    def __init__(self) -> None:
        super().__init__()
        self.requestTimer = None
        self.cemetaryMapLoadedListener = None

    def run(self) -> bool:
        self.phenixMapId = Kernel().playedCharacterUpdatesFrame._phenixMapId
        if not PlayedCharacterManager().currentMap:
            return self.once_map_processed(self.start)
        self.on(KernelEvent.PlayerStateChanged, self.onPlayerStateChange)
        if PlayerLifeStatusEnum(PlayedCharacterManager().state) == PlayerLifeStatusEnum.STATUS_PHANTOM:
            Logger().debug(f"Traveling to phenix map {self.phenixMapId}")
            self.autoTrip(dstMapId=self.phenixMapId, callback=self.onPhenixMapReached)
        elif PlayerLifeStatusEnum(PlayedCharacterManager().state) == PlayerLifeStatusEnum.STATUS_TOMBSTONE:
            self.cemetaryMapLoadedListener = self.once_map_processed(self.onCemetaryMapLoaded)
            self.releaseSoulRequest()

    def onPlayerStateChange(self, event, playerState: PlayerLifeStatusEnum, phenixMapId):
        self.phenixMapId = phenixMapId
        Logger().debug(f"Phoenix mapId : {phenixMapId}")
        if playerState == PlayerLifeStatusEnum.STATUS_PHANTOM:
            Logger().info(f"Player soul released waiting for cemetery map to load.")
        elif playerState == PlayerLifeStatusEnum.STATUS_ALIVE_AND_KICKING:
            Logger().info("Player is alive and kicking.")
            self.finish(True, None)

    def onCemetaryMapLoaded(self, event_id=None):
        Logger().debug(f"Cemetery map loaded.")
        if self.requestTimer:
            self.requestTimer.cancel()
        self.autoTrip(dstMapId=self.phenixMapId, callback=self.onPhenixMapReached)

    def onPhenixMapReached(self, code, error):
        if error:
            return self.finish(code, error)
        if Kernel().interactiveFrame:
            reviveIE = Kernel().interactiveFrame.getReviveIe()
            def onPhenixSkillUsed(code, error, iePosition=None):
                if error:
                    return self.finish(code, error)
                Logger().info("Phenix revive skill used")
            self.useSkill(ie=reviveIE, callback=onPhenixSkillUsed)
        else:
            self.onceFramePushed("RoleplayInteractivesFrame", self.onPhenixMapReached)
            
    def onCemetaryMapLoadedTimeout(self):
        Logger().error("Cemetary map loaded timeout.")
        self.cemetaryMapLoadedListener.delete()
        self.autoTrip(dstMapId=self.phenixMapId, callback=self.onPhenixMapReached)
            
    def releaseSoulRequest(self):
        self.requestTimer = BenchmarkTimer(self.CEMETARY_MAP_LOADED_TIMEOUT, self.onCemetaryMapLoadedTimeout)
        self.requestTimer.start()
        ConnectionsHandler().send(GameRolePlayFreeSoulRequestMessage())
