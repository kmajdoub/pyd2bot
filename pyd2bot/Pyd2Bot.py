from pyd2bot.BotSettings import BotSettings
from pyd2bot.data.enums import SessionTypeEnum
from pyd2bot.logic.roleplay.behaviors.bidhouse.MarketPersistenceManager import MarketPersistenceManager
from pyd2bot.logic.roleplay.behaviors.chat.SpammerBehavior import SmartSpammerBehavior
from pyd2bot.logic.roleplay.behaviors.updates.AutoUpgradeStats import AutoUpgradeStats
from pyd2bot.logic.roleplay.behaviors.updates.CollectStats import CollectStats
from pyd2bot.logic.common.frames.BotRPCFrame import BotRPCFrame
from pyd2bot.logic.common.frames.BotWorkflowFrame import BotWorkflowFrame
from pyd2bot.logic.fight.frames.FightAIFrame import FightAIFrame
from pyd2bot.logic.fight.frames.MuleFightFrame import MuleFightFrame
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.farm.MultiplePathsResourceFarm import MultiplePathsResourceFarm
from pyd2bot.logic.roleplay.behaviors.farm.ResourceFarm import ResourceFarm
from pyd2bot.logic.roleplay.behaviors.fight.GroupLeaderFarmFights import GroupLeaderFarmFights
from pyd2bot.logic.roleplay.behaviors.fight.MuleFighter import MuleFighter
from pyd2bot.logic.roleplay.behaviors.fight.SoloFarmFights import SoloFarmFights
from pyd2bot.logic.roleplay.behaviors.quest.treasure_hunt.ClassicTreasureHunt import ClassicTreasureHunt
from pyd2bot.data.models import Session
from pyd2bot.misc.BotEventsManager import BotEventsManager
from pyd2bot.misc.NapManager import NapManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.DisconnectionReasonEnum import DisconnectionReasonEnum
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InactivityManager import InactivityManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.DofusClient import DofusClient

class Pyd2Bot(DofusClient):

    def __init__(self, session: Session):
        self.session = session
        self._mule = session.isMuleFighter
        BotSettings.checkBreed(session)
        super().__init__(session.character.accountId)
        self.setAutoServerSelection(session.character.serverId, session.character.id)
        self.setCredentials(session.credentials.apikey, session.credentials.certId, session.credentials.certHash)
        self._state_update_listeners = []
        self._nap_manager:NapManager = None
        self._stats_collector = None
        self._main_behavior = None
        self._stats_auto_upgrade = None
        self._saved_player_stats = None
        self._old_saved_kamas = None
        self.session_run_id = None
        self._market_persistence_manager = None

    def shutdown(self, message="", reason=None):
        if self._main_behavior:
            behavior = None
            if isinstance(self._main_behavior, ResourceFarm):
                behavior = self._main_behavior
            elif isinstance(self._main_behavior, MultiplePathsResourceFarm):
                behavior = self._main_behavior._current_running_behavior
            if behavior and behavior.current_session_id is not None:
                behavior.resource_tracker.end_farm_session(
                    behavior.current_session_id,
                    behavior.session_resources
                )
                Logger().debug(f"Farm stat Session {behavior.current_session_id} ended")
        return super().shutdown(message, reason)

    def onReconnect(self, event, message, afterTime=0):
        AbstractBehavior.clear_children()
        if self._stats_collector:
            self._saved_player_stats = self._stats_collector.sessionStats # save player stats before restarting
            self._old_saved_kamas = self._stats_collector._old_saved_kamas
        return super().onReconnect(event, message, afterTime)

    def onInGame(self):
        Logger().info(f"Character {self.name} is now in game.")
        if self.session.isSeller:
            BotSettings.SELLER_VACANT.set()
        self.notifyOtherBots()
        self.startMainBehavior()

    def notifyOtherBots(self):
        for instId, inst in BotEventsManager.getInstances():
            if instId != self.name:
                inst.send(BotEventsManager.BOT_CONNECTED, self.name)

    def onFight(self, event):
        if not self._mule:
            Kernel().worker.addFrame(FightAIFrame(self.session))
        else:
            Kernel().worker.addFrame(MuleFightFrame(self.session.leader))

    def addUpdateListener(self, callback):
        self._state_update_listeners.append(callback)

    def addStatusChangeListener(self, callback):
        self._statusChangedListeners.append(callback)
        
    def startMainBehavior(self): 
        mainBehavior = None
        
        if self.session.isFarmSession:
            Logger().info(f"Starting farm behavior for {self.name}")
            mainBehavior = ResourceFarm(self.session.getPathFromDto(), self.session.jobFilters)

        elif self.session.isMultiPathsFarmer:
            Logger().info(f"Starting multi paths farmer behavior for {self.name}")
            mainBehavior = MultiplePathsResourceFarm(
                self.session.getPathsListFromDto(), self.session.jobFilters, self.session.numberOfCovers
            )

        elif self.session.type == SessionTypeEnum.GROUP_FIGHT:
            Logger().info(f"Starting group fight behavior for {self.name}")
            mainBehavior = GroupLeaderFarmFights(
                self.session.character,
                self.session.getPathFromDto(),
                self.session.fightsPerMinute,
                self.session.fightPartyMembers,
                self.session.monsterLvlCoefDiff,
                self.session.followers
            )

        elif self.session.type == SessionTypeEnum.SOLO_FIGHT:
            Logger().info(f"Starting solo fight behavior for {self.name}")
            mainBehavior = SoloFarmFights(
                self.session.getPathFromDto(),
                self.session.fightsPerMinute,
                self.session.fightPartyMembers,
                self.session.monsterLvlCoefDiff
            )

        elif self.session.isMuleFighter:
            Logger().info(f"Starting mule fighter behavior for {self.name}")
            mainBehavior = MuleFighter(self.session.leader)

        elif self.session.isTreasureHuntSession:
            Logger().info(f"Starting treasure hunt behavior for {self.name}")
            mainBehavior = ClassicTreasureHunt()
            
        if mainBehavior:
            mainBehavior.start(callback=self._on_main_behavior_finish)

        self._main_behavior = mainBehavior

    def _on_main_behavior_finish(self, code, err):
        self._main_behavior = None
        
        if err:
            Logger().error(err, exc_info=True)
            self.shutdown(DisconnectionReasonEnum.EXCEPTION_THROWN, err)
            return
            
        if self._nap_manager and self._nap_manager.is_napping():
            nap_duration = self._nap_manager.get_nap_duration()
            self.onReconnect(None, f"Taking a nap for {nap_duration} minutes", afterTime=int(nap_duration * 60))
            return

        self.shutdown(DisconnectionReasonEnum.WANTED_SHUTDOWN, f"Main behavior ended successfully with code {code}")

    def run(self):
        self.registerInitFrame(BotWorkflowFrame(self.session))
        self.registerInitFrame(BotRPCFrame())
        return super().run()

    def onCharacterSelectionSuccess(self, event, characterBaseInformations):
        super().onCharacterSelectionSuccess(event, characterBaseInformations)
        self._stats_collector = CollectStats(self._state_update_listeners, self._saved_player_stats)
        self._stats_collector.sessionStats.isSleeping = False
        self._stats_collector._old_saved_kamas = self._old_saved_kamas
        self._stats_collector.start()
        self._stats_auto_upgrade = AutoUpgradeStats(self.session.character.primaryStatId)
        self._stats_auto_upgrade.start()
        self._market_persistence_manager = MarketPersistenceManager(self)
        self._market_persistence_manager.start()
        self._nap_manager = NapManager(self)
