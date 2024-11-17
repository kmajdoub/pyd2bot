from pyd2bot.data.models import Character, Session
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.enums.FightOptionsEnum import FightOptionsEnum
from pydofus2.com.ankamagames.dofus.network.messages.game.context.GameContextKickMessage import GameContextKickMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightOptionToggleMessage import GameFightOptionToggleMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightReadyMessage import GameFightReadyMessage
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pyd2bot.logic.fight.frames.FightAIFrame import FightAIFrame

class FightPreparation(AbstractBehavior):
    def __init__(self):
        super().__init__()
        self._challenge_chosen = False
        self._fight_closed = False
        self._spectators_allowed = True

    @property
    def session(self) -> "Session":
        return self.fight_frame.session

    @property
    def fight_frame(self) -> "FightAIFrame":
        return Kernel().worker.getFrameByName("FightAIFrame")

    def run(self) -> bool:
        self.once(KernelEvent.FightResumed, self.onFightResumed)
        self.on(KernelEvent.FighterShowed, self.onFighterShowed)
        self.once(KernelEvent.FightJoined, self.onFightJoined)        
        self.on(
            KernelEvent.ChallengeBonusSelected,
            self.onChallengeBonusChosen,
            timeout=5,
            ontimeout=lambda _: self.onChallengeBonusChosen(None, "N/A"),
        )
        self.on(KernelEvent.ServerTextInfo, self.onServerTextInfo)

    def onServerTextInfo(self, event, msgId, msgType, textId, text, params):
        if textId == 4977: # resuming fight
            Logger().info("Fighter resumed the fight")
            self._fight_resumed = True
        elif textId == 4777: # Fight closed
            self._fight_closed = True
        elif textId == 4907: # Fight open
            self._fight_closed = False
            self.requestClosedFight()
        elif textId == 412242: # Spectators allowed
            self._spectators_allowed = True
            self.session.fightSecret = False
            self.requestFightSecret()
        elif textId == 412243: # Spectators disallowed
            self._spectators_allowed = False
            self.session.fightSecret = True

    def onFightResumed(self, event):
        Logger().warning("Fight resumed in after reconnect!")
        self._fight_resumed = True

    def onFightJoined(self, event, isFightStarted, fightType, isTeamPhase, timeMaxBeforeFightStart):
        self._fight_ready_sent = False
        if self.session.isLeader:
            self.requestFightSecret()
            self.requestClosedFight()

    def onChallengeBonusChosen(self, event, bonusId):
        if not self._challenge_chosen:
            self._challenge_chosen = True
            if self.session.isLeader:
                Logger().info(f"Challenge bonus {bonusId} chosen.")
                if self.allMembersJoinedFight():
                    self.sendFightReady()
                else:
                    Logger().info("Waiting for members to join fight.")

    def requestFightSecret(self):
        if not self.session.fightSecret and self._spectators_allowed:
            message = GameFightOptionToggleMessage()
            message.init(FightOptionsEnum.FIGHT_OPTION_SET_SECRET)
            ConnectionsHandler().send(message)

    def requestClosedFight(self):
        if not self.session.followers and not self._fight_closed:
            message = GameFightOptionToggleMessage()
            message.init(FightOptionsEnum.FIGHT_OPTION_SET_CLOSED)
            ConnectionsHandler().send(message)

    def onFighterShowed(self, event, fighterId):
        if self.session.isLeader:
            self._my_turn = False
            if fighterId > 0:
                player = self.session.getPlayerById(fighterId)
                if player:
                    if player.id != self.session.character.id:
                        self.onMemberJoinedFight(player)
                    else:
                        Logger().info(f"Party Leader {player.name} joined fight.")
                else:
                    Logger().error(f"Unknown Player {fighterId} joined fight.")
                    self.requestClosedFight()
                    self.kickPlayerFromFight(fighterId)   
            else:
                Logger().info(f"Monster {fighterId} appeared.")

    def kickPlayerFromFight(self, fighterId):
        message = GameContextKickMessage()
        message.init(fighterId)
        ConnectionsHandler().send(message)

    def allMembersJoinedFight(self) -> bool:
        if Kernel().fightEntitiesFrame:
            for member in self.session.fightPartyMembers:
                if not Kernel().fightEntitiesFrame.getEntityInfos(member.id):
                    return False
        return True

    def onMemberJoinedFight(self, player: Character):
        Logger().info(f"Follower '{player.name}' joined fight.")
        if self._fight_resumed:
            return Logger().warning("Fight resumed so wont check if members joined or not.")
        if self._fight_ready_sent:
            return Logger().warning("Fight ready already sent so we wont check if members joined or not.")
        playerManager = PlayedCharacterManager.getInstance(player.accountId)
        if not playerManager:
            return Logger().error(f"Player manager not found for {player.name}, probably disconnected")
        playerManager.isFighting = True
        self.sendFightReady(player.accountId) # for other party members on their behalf
        if self.allMembersJoinedFight():
            Logger().info(f"All party members joined fight.")
            if self._challenge_chosen:
                self.sendFightReady() # for leader at the end
                self.finish(0)
            self._fight_ready_sent = True
        else:
            missing = [
                m.name for m in self.session.fightPartyMembers if not Kernel().fightEntitiesFrame.getEntityInfos(m.id)
            ]
            Logger().info(f"Members missing : {missing}")

    def sendFightReady(self, accountId=None):
        startFightMsg = GameFightReadyMessage()
        startFightMsg.init(True)
        connh = ConnectionsHandler.getInstance(accountId) if accountId else ConnectionsHandler()
        connh.send(startFightMsg)