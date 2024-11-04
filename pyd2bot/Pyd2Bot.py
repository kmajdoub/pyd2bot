import random

from pyd2bot.BotSettings import BotSettings
from pyd2bot.data.enums import SessionTypeEnum
from pyd2bot.logic.roleplay.behaviors.bank.RetrieveFromBank import RetrieveFromBank
from pyd2bot.logic.roleplay.behaviors.bidhouse.MonitorMarket import MonitorMarket
from pyd2bot.logic.roleplay.behaviors.bidhouse.RetrieveAndSell import RetrieveAndSell
from pyd2bot.logic.roleplay.behaviors.bidhouse.SellItemsFromBag import SellItemsFromBag
from pyd2bot.logic.roleplay.behaviors.bidhouse.UpdateBids import UpdateBidsBehavior
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
from pyd2bot.logic.roleplay.messages.TakeNapMessage import TakeNapMessage
from pyd2bot.misc.BotEventsManager import BotEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.DisconnectionReasonEnum import DisconnectionReasonEnum
from pydofus2.com.ankamagames.dofus.network.enums.BreedEnum import BreedEnum
from pydofus2.com.ankamagames.dofus.types.enums.ItemCategoryEnum import ItemCategoryEnum
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.DofusClient import DofusClient


class Pyd2Bot(DofusClient):

    def __init__(self, session: Session):
        self.session = session
        self._mule = session.isMuleFighter
        self.checkBreed(session)
        super().__init__(session.character.accountId)
        self.setAutoServerSelection(session.character.serverId, session.character.id)
        self.setCredentials(session.credentials.apikey, session.credentials.certId, session.credentials.certHash)
        self._stateUpdateListeners = []
        self._taking_a_nap = False
        self._nap_duration = None
        self._stats_collector = None
        self._main_behavior = None
        self._stats_auto_upgrade = None

    def checkBreed(self, session: Session):
        if session.character.breedId not in BotSettings.defaultBreedConfig:
            supported_breeds = [BreedEnum.get_name(breedId) for breedId in BotSettings.defaultBreedConfig]
            raise ValueError(
                f"Breed {session.character.breedName} is not supported, supported breeds are {supported_breeds}"
            )

    def onReconnect(self, event, message, afterTime=0):
        AbstractBehavior.clearAllChildren()
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
            Kernel().worker.addFrame(BotFightFrame(self.session))
        else:
            Kernel().worker.addFrame(BotMuleFightFrame(self.session.leader))

    def addUpdateListener(self, callback):
        self._stateUpdateListeners.append(callback)

    def addStatusChangeListener(self, callback):
        self._statusChangedListeners.append(callback)
        
    def startSessionMainBehavior(self):
        Logger().info(f"Starting main behavior for {self.name}, sessionType : {self.session.type.name}")
        self._main_behavior = RetrieveAndSell(312, 100)
        PIWI_FEATHER_GIDS = [6900, 6902, 6898, 6899, 6903, 6897]
        # items_gids = [(gid, 100) for gid in PIWI_FEATHER_GIDS]        
        # self._main_behavior = SellFromBagBehavior(items_gids)

        self._main_behavior = UpdateBidsBehavior(PIWI_FEATHER_GIDS, 100, 0, 0.25)
        self._main_behavior.start(callback=self.onMainBehaviorFinish)
        return
        
        BotEventsManager().on(
            BotEventsManager.TAKE_NAP, 
            self._on_take_nap, 
            originator=self
        )
                
        mainBehavior = None
        
        if self.session.isFarmSession:
            Logger().info(f"Starting farm behavior for {self.name}")
            mainBehavior = ResourceFarm(self.session.getPathFromDto(), self.session.jobFilters)
            mainBehavior.start(callback=self.onMainBehaviorFinish)

        elif self.session.isMultiPathsFarmer:
            Logger().info(f"Starting multi paths farmer behavior for {self.name}")
            mainBehavior = MultiplePathsResourceFarm(
                self.session.getPathsListFromDto(), self.session.jobFilters, self.session.numberOfCovers
            )
            mainBehavior.start(callback=self.onMainBehaviorFinish)

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
            mainBehavior.start(callback=self.onMainBehaviorFinish)

        elif self.session.type == SessionTypeEnum.SOLO_FIGHT:
            Logger().info(f"Starting solo fight behavior for {self.name}")
            mainBehavior = SoloFarmFights(
                self.session.getPathFromDto(),
                self.session.fightsPerMinute,
                self.session.fightPartyMembers,
                self.session.monsterLvlCoefDiff
            )
            mainBehavior.start(callback=self.onMainBehaviorFinish)

        elif self.session.isMuleFighter:
            Logger().info(f"Starting mule fighter behavior for {self.name}")
            mainBehavior = MuleFighter(self.session.leader)
            mainBehavior.start(callback=self.onMainBehaviorFinish)

        elif self.session.isTreasureHuntSession:
            Logger().info(f"Starting treasure hunt behavior for {self.name}")
            mainBehavior = ClassicTreasureHunt()
            mainBehavior.start(callback=self.onMainBehaviorFinish)

        elif self.session.isMixed:
            mainBehavior = random.choice([ResourceFarm(60 * 5), SoloFarmFights(60 * 3), ClassicTreasureHunt()])
            mainBehavior.start(callback=self.switchActivity)

        self._main_behavior = mainBehavior
        
        if not self.session.isMuleFighter:
            nap_timeout_hours = BotSettings.generate_random_nap_timeout()
            
            self.nap_take_timer = BenchmarkTimer(
                int(nap_timeout_hours * 60 * 60),
                lambda: self.onTakeNapTimer(mainBehavior),
            )
            
            self.nap_take_timer.start()

    def _on_take_nap(self, event, nap_duration):
        """Handle incoming nap notifications from leader"""
        Logger().info(f"[{self.name}] Received nap notification for {nap_duration} minutes")
        
        if not isinstance(nap_duration, int) or nap_duration <= 0:
            Logger().error(f"[{self.name}] Invalid nap duration received: {nap_duration}")
            return
            
        self._nap_duration = nap_duration
        self._taking_a_nap = True
        
        if self._main_behavior:
            Logger().info(f"[{self.name}] Stopping current behavior before nap")
            self._main_behavior.stop()
        else:
            Logger().info(f"[{self.name}] No active behavior, starting nap immediately")
            self.onReconnect(
                None,
                f"Taking a nap for {self._nap_duration} minutes",
                afterTime=int(self._nap_duration * 60),
            )

    def onMainBehaviorFinish(self, code, err):
        self._main_behavior = None
        
        if self._taking_a_nap:
            self._taking_a_nap = False
            if self._nap_duration is None:
                self._nap_duration = BotSettings.generate_random_nap_duration()
            self.onReconnect(
                None,
                "Taking a nap for %s minutes" % self._nap_duration,
                afterTime=int(self._nap_duration * 60),
            )
            return

        if err:
            Logger().error(err, exc_info=True)
            self.shutdown(DisconnectionReasonEnum.EXCEPTION_THROWN, err)
        else:
            self.shutdown(DisconnectionReasonEnum.WANTED_SHUTDOWN, "Main behavior ended successfully with code %s" % code)

    def onTakeNapTimer(self, mainBehavior: AbstractBehavior):
        """Handle nap timer expiration for leader"""
        self._taking_a_nap = True
        self._nap_duration = BotSettings.generate_random_nap_duration()
        
        # If this is a group leader, notify followers
        if self.session.type == SessionTypeEnum.GROUP_FIGHT:
            Logger().info(f"[{self.name}] Leader notifying {len(self.session.followers)} followers of {self._nap_duration} minute nap")
            for follower in self.session.followers:
                try:
                    follower_instance = Kernel.getInstance(follower.accountId)
                    if follower_instance:
                        follower_instance.worker.process(TakeNapMessage(self._nap_duration))
                        Logger().debug(f"[{self.name}] Sent nap notification to follower {follower.accountId}")
                    else:
                        Logger().warn(f"[{self.name}] Follower instance not found: {follower.accountId}")
                except Exception as e:
                    Logger().error(f"[{self.name}] Error notifying follower {follower.accountId}: {str(e)}")
        
        if mainBehavior:
            Logger().info(f"[{self.name}] Stopping behavior for nap")
            mainBehavior.stop()

    def switchActivity(self, code, err):
        self.onReconnect(None, f"Fake disconnect and take nap", afterTime=random.random() * 60 * 3)

    def run(self):
        self.registerInitFrame(BotWorkflowFrame(self.session))
        self.registerInitFrame(BotRPCFrame())
        return super().run()

    def onCharacterSelectionSuccess(self, event, characterBaseInformations):
        super().onCharacterSelectionSuccess(event, characterBaseInformations)
        self._stats_collector = CollectStats(self._stateUpdateListeners)
        self._stats_collector.start()
        self._stats_auto_upgrade = AutoUpgradeStats(self.session.character.primaryStatId)
        self._stats_auto_upgrade.start()
