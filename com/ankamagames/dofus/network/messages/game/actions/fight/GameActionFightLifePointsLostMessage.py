from com.ankamagames.dofus.network.messages.game.actions.AbstractGameActionMessage import AbstractGameActionMessage


class GameActionFightLifePointsLostMessage(AbstractGameActionMessage):
    protocolId = 4520
    targetId:float
    loss:int
    permanentDamages:int
    elementId:int
    
