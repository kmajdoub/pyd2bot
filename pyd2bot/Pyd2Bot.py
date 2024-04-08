import random

from pyd2bot.BotSettings import BotSettings
from pyd2bot.logic.roleplay.behaviors.updates.AutoUpgradeStats import AutoUpgradeStats
from pyd2bot.logic.roleplay.behaviors.updates.CollectStats import CollectStats
from pyd2bot.logic.common.frames.BotRPCFrame import BotRPCFrame
from pyd2bot.logic.common.frames.BotWorkflowFrame import BotWorkflowFrame
from pyd2bot.logic.common.rpcMessages.PlayerConnectedMessage import PlayerConnectedMessage
from pyd2bot.logic.fight.frames.BotFightFrame import BotFightFrame
from pyd2bot.logic.fight.frames.BotMuleFightFrame import BotMuleFightFrame
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.farm.MultiplePathsResourceFarm import MultiplePathsResourceFarm
from pyd2bot.logic.roleplay.behaviors.farm.ResourceFarm import ResourceFarm
from pyd2bot.logic.roleplay.behaviors.fight.GroupLeaderFarmFights import GroupLeaderFarmFights
from pyd2bot.logic.roleplay.behaviors.fight.MuleFighter import MuleFighter
from pyd2bot.logic.roleplay.behaviors.fight.SoloFarmFights import SoloFarmFights
from pyd2bot.logic.roleplay.behaviors.quest.ClassicTreasureHunt import ClassicTreasureHunt
from pyd2bot.data.models import Session
from pyd2bot.data.enums import SessionStatusEnum
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import MapDisplayManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionType import ConnectionType
from pydofus2.com.ankamagames.dofus.kernel.net.DisconnectionReasonEnum import DisconnectionReasonEnum
from pydofus2.com.ankamagames.dofus.network.enums.BreedEnum import BreedEnum
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.DofusClient import DofusClient


class Pyd2Bot(DofusClient):

    def __init__(self, session: Session):
        if session.character.breedId not in BotSettings.defaultBreedConfig:
            supported_breeds = [BreedEnum.get_name(breedId) for breedId in BotSettings.defaultBreedConfig]
            raise ValueError(
                f"Breed {session.character.breedName} is not supported, supported breeds are {supported_breeds}"
            )
        super().__init__(session.character.accountId)
        self.session = session
        self._mule = session.isMuleFighter
        self.setAutoServerSelection(session.character.serverId, session.character.id)
        self.setCredentials(session.credentials.apikey, session.credentials.certId, session.credentials.certHash)
        self._botUpdateStatsHandlers = []

    def onReconnect(self, event, message, afterTime=0):
        AbstractBehavior.clearAllChilds()
        return super().onReconnect(event, message, afterTime)

    def onInGame(self):
        Logger().info(f"Character {self.name} is now in game.")
        if self.session.isSeller:
            BotSettings.SELLER_VACANT.set()
        self.notifyOtherBots()
        self.startSessionMainBehavior()

    def notifyOtherBots(self):
        for instId, inst in Kernel.getInstances():
            if instId != self.name:
                inst.worker.process(PlayerConnectedMessage(self.name))

    def onFight(self, event):
        if not self._mule:
            Kernel().worker.addFrame(BotFightFrame())
        else:
            Kernel().worker.addFrame(BotMuleFightFrame(self.session.leader))

    def onMainBehaviorFinish(self, code, err):
        if err:
            Logger().error(err, exc_info=True)
            self.shutdown(DisconnectionReasonEnum.EXCEPTION_THROWN, err)
        else:
            self.shutdown(DisconnectionReasonEnum.WANTED_SHUTDOWN, "main behavior ended successfully")

    def registerBotStatsHandler(self, callback):
        self._botUpdateStatsHandlers.append(callback)

    def startSessionMainBehavior(self):
        Logger().info(f"Starting main behavior for {self.name}, sessionType : {self.session.type.name}")

        if self.session.isFarmSession:
            Logger().info(f"Starting farm behavior for {self.name}")
            ResourceFarm(self.session.getPathFromDto(), self.session.jobFilters).start()

        elif self.session.isMultiPathsFarmer:
            Logger().info(f"Starting multi paths farmer behavior for {self.name}")
            MultiplePathsResourceFarm(
                self.session.getPathsListFromDto(), self.session.jobFilters, self.session.numberOfCovers
            ).start(callback=self.onMainBehaviorFinish)

        elif self.session.isFightSession:
            Logger().info(f"Starting fight behavior for {self.name}")
            if self.session.isLeader:
                GroupLeaderFarmFights(
                    self.session.getPathFromDto(),
                    self.session.fightsPerMinute,
                    self.session.fightPartyMembers,
                    self.session.monsterLvlCoefDiff,
                    self.session.followers
                ).start(callback=self.onMainBehaviorFinish)
            else:
                SoloFarmFights(
                    self.session.getPathFromDto(),
                    self.session.fightsPerMinute,
                    self.session.fightPartyMembers,
                    self.session.monsterLvlCoefDiff
                ).start(callback=self.onMainBehaviorFinish)

        elif self.session.isMuleFighter:
            Logger().info(f"Starting mule fighter behavior for {self.name}")
            MuleFighter(self.session.leader).start(callback=self.onMainBehaviorFinish)

        elif self.session.isTreasureHuntSession:
            Logger().info(f"Starting treasure hunt behavior for {self.name}")
            ClassicTreasureHunt().start(callback=self.onMainBehaviorFinish)

        elif self.session.isMixed:
            activity = random.choice([ResourceFarm(60 * 5), SoloFarmFights(60 * 3)])
            activity.start(callback=self.switchActivity)

        self.nap_take_timer = BenchmarkTimer(
            BotSettings.TAKE_NAP_AFTTER_HOURS * 60 * 60,
            lambda: self.onReconnect(
                None,
                "Taking a nap for %s minutes" % BotSettings.NAP_DURATION_MINUTES,
                afterTime=BotSettings.NAP_DURATION_MINUTES * 60,
            ),
        )
        self.nap_take_timer.start()

    def switchActivity(self, code, err):
        self.onReconnect(None, f"Fake disconnect and take nap", afterTime=random.random() * 60 * 3)

    def run(self):
        self.registerInitFrame(BotWorkflowFrame(self.session))
        self.registerInitFrame(BotRPCFrame())
        return super().run()

    def onCharacterSelectionSuccess(self, event, characterBaseInformations):
        super().onCharacterSelectionSuccess(event, characterBaseInformations)
        CollectStats(self._botUpdateStatsHandlers).start()
        AutoUpgradeStats(self.session.character.primaryStatId).start()
        
    def getState(self):
        if self.terminated.is_set():
            if self._banned:
                return SessionStatusEnum.BANNED
            if self._crashed:
                return SessionStatusEnum.CRASHED
            return SessionStatusEnum.TERMINATED
        if (
            not ConnectionsHandler.getInstance(self.name)
            or ConnectionsHandler.getInstance(self.name).connectionType == ConnectionType.DISCONNECTED
        ):
            if self._banned:
                return SessionStatusEnum.BANNED
            return SessionStatusEnum.DISCONNECTED
        elif ConnectionsHandler.getInstance(self.name).connectionType == ConnectionType.TO_LOGIN_SERVER:
            return SessionStatusEnum.AUTHENTICATING
        if Kernel.getInstance(self.name).fightContextFrame:
            return SessionStatusEnum.FIGHTING
        elif not Kernel.getInstance(self.name).roleplayEntitiesFrame:
            return SessionStatusEnum.OUT_OF_ROLEPLAY
        elif MapDisplayManager.getInstance(self.name).currentDataMap is None:
            return SessionStatusEnum.LOADING_MAP
        elif not Kernel.getInstance(self.name).roleplayEntitiesFrame.mcidm_processed:
            return SessionStatusEnum.PROCESSING_MAP
        if AbstractBehavior.hasRunning(self.name):
            return SessionStatusEnum.ROLEPLAYING
        return SessionStatusEnum.IDLE
