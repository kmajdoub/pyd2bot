import random
from datetime import datetime, timedelta
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.chat.GetAllMapFightsDetails import GetMapFightDetails
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InactivityManager import InactivityManager
from pydofus2.com.ankamagames.dofus.network.messages.game.chat.ChatClientMultiMessage import ChatClientMultiMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.chat.ChatServerMessage import ChatServerMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.chat.channel.ChannelEnablingMessage import ChannelEnablingMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapRunningFightDetailsMessage import MapRunningFightDetailsMessage
from pydofus2.com.ankamagames.dofus.network.types.game.context.fight.GameFightFighterNamedLightInformations import GameFightFighterNamedLightInformations
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.GameRolePlayHumanoidInformations import GameRolePlayHumanoidInformations
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

class SmartSpammerBehavior(AbstractBehavior):
    def __init__(self):
        super().__init__()
        self.min_interval = 45
        self.max_interval = 90
        self.slow_min_interval = 60 * 15  # 25 minutes
        self.slow_max_interval = 60 * 35  # 35 minutes
        self.send_message_timer = None

        # Target tracking
        self.target_name = "Whitte-Beardd"
        self.target_present = False
        self.target_infos = None
        self.target_in_fight = False
        self.general_channel_activated = False
        
        # Channel configuration with cooldowns
        self.channel_configs = {
            0: {"cooldown_minutes": 3},    # General
            5: {"cooldown_minutes": 30},    # Trade
            14: {"cooldown_minutes": 50}    # Community
        }
        self.channel_cooldowns = {channel: datetime.min for channel in self.channel_configs}
        self.last_channel = None
        
        # Activity hours (0=inactive, 1=normal, 2=high)
        self.active_hours = {
            0: 2,  1:2,  2: 2,  3: 0,    4: 0,    5: 0.2,
            6: 0.5,  7: 1,    8: 1,    9: 1.5,  10: 1.5, 11: 1.5,
            12: 1.5, 13: 1.5, 14: 1.5, 15: 1.5, 16: 1.5, 17: 2,
            18: 2,   19: 2,   20: 2,   21: 2, 22: 2,   23: 2
        }
        
        # Message system
        self.messages = [
            "/!\ white-beard ARNAQUEUR: 17M payés pour pl -> kick après 9/50 combats, refuse remboursement",
            "ATTENTION: white-beard m'a pris hier 17M d'avance pour pl, m'a kick après 9 combats car je voulais pas continuer avec lui et garde toujours mes kamas",
            "whitte-beardd m'a déjà arnaqué plus de 13m en total faites pas confiance il y'a moins cher et plus confiance",
        ]
        self.message_cooldowns = {msg: datetime.min for msg in self.messages}
    
    def stop(self):
        if hasattr(self, 'send_message_timer') and self.send_message_timer:
            self.send_message_timer.cancel()

    def run(self, *args, **kwargs):
        self.on(KernelEvent.ChannelActivated, self._on_channel_activated)
        self.on(KernelEvent.ActorShowed, self._on_actor_showed)
        self.on(KernelEvent.EntityVanished, self._on_actor_removed)
        self.on(KernelEvent.ChatMessage, self._on_chat_message)
        
        # Check if target is already on map using RoleplayEntitiesFrame
        roleplay_frame = Kernel().roleplayEntitiesFrame
        if roleplay_frame and roleplay_frame._entities:
            for entity_id, entity in roleplay_frame._entities.items():
                if isinstance(entity, GameRolePlayHumanoidInformations):
                    if self.target_name.lower() in entity.name.lower():
                        self.target_infos = entity
                        self.target_present = True
                        Logger().info(f"Target {self.target_name} found on map during initialization!")
                        return self.send_channel_general_enable()
                        
        if Kernel().roleplayEntitiesFrame._fights:
            Logger().debug(f"Found following fights in the map : {list(Kernel().roleplayEntitiesFrame._fights.keys())}")
            GetMapFightDetails().start(callback=self._on_map_fights_details, parent=self)
            return
        else:
            Logger().debug("No fight found in the map")
            

        self.send_channel_general_enable()

    def _on_chat_message(self, event, msg: ChatServerMessage):
        if msg.senderName in ["White-Bbeard-Kill", "Whitte-Beardd", "White-Beard-Kg", "White-Beard-Yonko"]:
            content = self.select_message()
        
            message = ChatClientMultiMessage()
            message.init(msg.channel, content)
            
            ConnectionsHandler().send(message)
            Logger().info(f"Sent message in channel {0}: {content}")

    def _on_map_fights_details(self, code, error, fights_details: list[MapRunningFightDetailsMessage]):
        for details in fights_details:
            for attacker in details.attackers:
                if isinstance(attacker, GameFightFighterNamedLightInformations):
                    if attacker.name == self.target_name:
                        self.target_infos = attacker
                        self.target_present = True
                        self.target_in_fight = True
                        Logger().info(f"target {self.target_name} found in combat")
                        break
        self.send_channel_general_enable()

    def _on_channel_activated(self, event, channel, enable):
        if channel == 0:
            self.general_channel_activated = True
            self.send_chat_message()

    def _on_actor_showed(self, event, infos: "GameRolePlayHumanoidInformations"):
        Logger().info(f"Actor {infos.name} showed.")
        if self.target_name.lower() in infos.name.lower():
            self.target_in_fight = False
            self.target_infos = infos
            Logger().info(f"Target {self.target_name} detected on map!")
            self.target_present = True
            # Reset timer with faster interval when target appears
            if hasattr(self, 'send_message_timer') and self.send_message_timer:
                self.send_message_timer.cancel()
            self.send_chat_message()

    def _on_actor_removed(self, event, actor_id):
        if self.target_infos:
            if isinstance(self.target_infos, GameRolePlayHumanoidInformations):
                target_id = self.target_infos.contextualId
            elif isinstance(self.target_infos, GameFightFighterNamedLightInformations):
                target_id = self.target_infos.id
            if target_id == actor_id:
                self.target_infos = None
                self.target_present = False
                Logger().info(f"Target {self.target_name} disappeared")
                # Reset timer with slower interval when target might be gone
                if hasattr(self, 'send_message_timer') and self.send_message_timer:
                    self.send_message_timer.cancel()
                self.send_chat_message()
        
    def get_next_interval(self) -> int:
        if self.target_present:
            # Normal intervals when target is present
            activity_weight = self.active_hours.get(datetime.now().hour, 1.0)
            base_interval = random.uniform(self.min_interval, self.max_interval)
            return int(base_interval * 3) if activity_weight == 0 else int(base_interval / activity_weight)
        else:
            # Slow intervals when target is absent
            return int(random.uniform(self.slow_min_interval, self.slow_max_interval))

    def select_channel(self) -> int:
        now = datetime.now()
        if self.target_present:
            # When target is present, prefer general channel
            if now - self.channel_cooldowns[0] >= timedelta(minutes=self.channel_configs[0]["cooldown_minutes"]):
                return 0
            
        # Get available channels based on cooldowns
        available_channels = [
            channel for channel, config in self.channel_configs.items()
            if now - self.channel_cooldowns[channel] >= timedelta(minutes=config["cooldown_minutes"])
            and (self.target_present or channel != 0)  # Skip general channel if target not present
        ]
        
        if not available_channels:
            return min(
                self.channel_configs.keys(),
                key=lambda c: self.channel_cooldowns[c] + timedelta(minutes=self.channel_configs[c]["cooldown_minutes"])
            )
        
        if self.last_channel in available_channels and len(available_channels) > 1:
            available_channels.remove(self.last_channel)
            
        return random.choice(available_channels)

    def send_channel_general_enable(self):
        msg = ChannelEnablingMessage()
        msg.init(0, True)
        ConnectionsHandler().send(msg)

    def select_message(self) -> str:
        now = datetime.now()
        available_messages = [
            msg for msg in self.messages
            if now - self.message_cooldowns[msg] > timedelta(minutes=5)
        ]
        
        if not available_messages:
            return random.choice(self.messages)
        
        return random.choice(available_messages)

    def send_chat_message(self):
        channel = self.select_channel()
        if channel == 0 and not self.target_infos and not self.target_in_fight:
            return

        content = self.select_message()
        
        message = ChatClientMultiMessage()
        message.init(channel, content)
        
        ConnectionsHandler().send(message)
        Logger().info(f"Sent message in channel {channel}: {content}")
        InactivityManager().activity()

        now = datetime.now()
        self.message_cooldowns[content] = now
        self.channel_cooldowns[channel] = now
        self.last_channel = channel
        
        interval = self.get_next_interval()
        if self.send_message_timer:
            self.send_message_timer.cancel()
        Logger().debug(f"Sending next message in : {interval / 60:.2f} minutes")
        self.send_message_timer = BenchmarkTimer(interval, self.send_chat_message)
        self.send_message_timer.start()
