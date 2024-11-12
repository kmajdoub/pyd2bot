from typing import Optional, TYPE_CHECKING
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pyd2bot.misc.BotEventsManager import BotEventsManager
from pyd2bot.BotSettings import BotSettings

if TYPE_CHECKING:
    from pyd2bot.Pyd2Bot import Pyd2Bot

class NapManager:
    def __init__(self, client: "Pyd2Bot"):
        self.client = client
        self._taking_a_nap = False
        self._nap_duration: Optional[int] = None
        self._nap_take_timer = None
        self.logger = Logger()
        
        BotEventsManager().once(
            BotEventsManager.events.TAKE_NAP, 
            self._on_nap_notification
        )

        if not self.client.session.isMuleFighter:
            self._schedule_next_nap()

    def _schedule_next_nap(self) -> None:
        nap_timeout = BotSettings.generate_random_nap_timeout() * 60 * 60  # Convert hours to seconds
        self._nap_take_timer = BenchmarkTimer(int(nap_timeout), self._initiate_nap)
        BotEventsManager().send(BotEventsManager.events.TimeToNextNap, int(nap_timeout))
        self._nap_take_timer.start()

    def _on_nap_notification(self, event, nap_duration: int) -> None:
        """Handle incoming nap notifications from leader"""
        self.logger.info(f"[{self.client.name}] Received nap notification for {nap_duration} minutes")
        self._nap_duration = nap_duration
        self._taking_a_nap = True
        self._send_update_to_front()
        self._handle_nap_start(nap_duration)

    def _handle_nap_start(self, nap_duration: Optional[int] = None) -> None:
        if nap_duration is None:
            nap_duration = BotSettings.generate_random_nap_duration()

        if self.client._main_behavior:
            self.client._main_behavior.stop()
            
        self.client.onReconnect(
            None,
            f"Taking a nap for {nap_duration} minutes",
            afterTime=int(nap_duration * 60)
        )

    def _initiate_nap(self) -> None:
        self._taking_a_nap = True
        self._nap_duration = BotSettings.generate_random_nap_duration()
        self._send_update_to_front()
        
        if hasattr(self.client.session, 'followers') and self.client.session.followers:
            self._notify_followers()
            
        self._handle_nap_start(self._nap_duration)

    def _notify_followers(self) -> None:
        for follower in self.client.session.followers:
            follower_events = BotEventsManager.getInstance(follower.accountId)
            if follower_events:
                follower_events.send(BotEventsManager.events.TAKE_NAP, self._nap_duration)

    def _send_update_to_front(self) -> None:
        if self.client._stats_collector:
            self.client._stats_collector.playerStats.timeSpentSleeping += self._nap_duration
            self.client._stats_collector.playerStats.isSleeping = True
            self.client._stats_collector.onPlayerUpdate(KernelEvent.Paused)

    def is_napping(self) -> bool:
        return self._taking_a_nap

    def get_nap_duration(self) -> Optional[int]:
        return self._nap_duration

    def reset(self) -> None:
        self._taking_a_nap = False
        self._nap_duration = None
        if self._nap_take_timer:
            self._nap_take_timer.cancel()