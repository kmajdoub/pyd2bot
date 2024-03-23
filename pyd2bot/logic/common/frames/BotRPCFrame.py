import threading

from pyd2bot.logic.common.rpcMessages.ComeToCollectMessage import \
    ComeToCollectMessage
from pyd2bot.logic.common.rpcMessages.GetCurrentVertexMessage import \
    GetCurrentVertexMessage
from pyd2bot.logic.common.rpcMessages.GetStatusMessage import GetStatusMessage
from pyd2bot.logic.common.rpcMessages.RCPResponseMessage import RPCResponseMessage
from pyd2bot.logic.common.rpcMessages.RPCMessage import RPCMessage
from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.logic.roleplay.behaviors.exchange.CollectItems import CollectItems
from pyd2bot.logic.roleplay.behaviors.movement.AutoTrip import AutoTrip
from pyd2bot.logic.roleplay.behaviors.movement.ChangeMap import ChangeMap
from pyd2bot.logic.roleplay.messages.FollowTransitionMessage import FollowTransitionMessage
from pyd2bot.logic.roleplay.messages.MoveToVertexMessage import MoveToVertexMessage
from pyd2bot.logic.roleplay.messages.SellerVacantMessage import SellerVacantMessage
from pyd2bot.misc.BotEventsmanager import BotEventsManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.types.MovementFailError import \
    MovementFailError
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import \
    BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority


class BotRPCFrame(Frame):
    DEST_KERNEL_NOT_FOUND = "dest kernel not found"
    CALL_TIMEOUT = "call timeout"
    
    def __init__(self):
        self._waitingForResp = {}
        super().__init__()

    def pushed(self) -> bool:
        return True

    def pulled(self) -> bool:
        return True

    @property
    def priority(self) -> int:
        return Priority.HIGHEST

    def process(self, msg: RPCMessage) -> bool:
        if isinstance(msg, RPCMessage):
            if isinstance(msg, RPCResponseMessage):
                if msg.reqUid in self._waitingForResp:
                    respw = self._waitingForResp[msg.reqUid]
                    respw["timeout"].cancel()
                    del respw["timeout"]
                    if "callback" in respw:
                        self._waitingForResp.pop(msg.reqUid)
                        if respw["callback"] is not None:
                            respw["callback"](result=msg.data, error=None, sender=msg.sender)
                    if "event" in respw:
                        respw["result"] = msg.data
                        respw["event"].set()
                else:
                    Logger().warn("RPCResponseMessage without waiting caller")
                return True

            if isinstance(msg, GetStatusMessage):
                from pyd2bot.apis.PlayerAPI import PlayerAPI
                rsp = RPCResponseMessage(msg, data=PlayerAPI().status)
                self.send(rsp)
                return True

            elif isinstance(msg, GetCurrentVertexMessage):
                rsp = RPCResponseMessage(msg, data=PlayedCharacterManager().currVertex)
                self.send(rsp)
                return True

            elif isinstance(msg, ComeToCollectMessage):
                def onresponse(result, error):
                    if error:
                        Logger().error(f"[RPCFrame] Error while trying to meet the guest {msg.guestInfos.login} to collect resources: {error}")
                    for _, instance in Kernel.getInstances():
                        instance.worker.process(SellerVacantMessage(threading.current_thread().name))
                    BotConfig.SELLER_VACANT.set()
                    if BotConfig.SELLER_LOCK.locked():
                        BotConfig.SELLER_LOCK.release()
                if CollectItems().isRunning():
                    Logger().error(f"[RPCFrame] can't start collect with {msg.guestInfos.login} because collect is already running with {CollectItems().guest.login}")
                    rsp = RPCResponseMessage(msg, data=False)
                    self.send(rsp)
                    return True
                rsp = RPCResponseMessage(msg, data=True)
                self.send(rsp)
                CollectItems().start(msg.bankInfos, msg.guestInfos, None, callback=onresponse)
                return True
        
        elif isinstance(msg, MoveToVertexMessage):
            BotEventsManager().send(BotEventsManager.MOVE_TO_VERTEX, msg.vertex)
            return True
        
        elif isinstance(msg, FollowTransitionMessage):
            Logger().info(f"Will follow transision {msg.transition}")
            if msg.transition.transitionMapId == PlayedCharacterManager().currentMap.mapId:
                Logger().warning(
                    f"Transition is heading to my current map ({msg.transition.transitionMapId}), nothing to do."
                )
            else:
                def onresp(errType, error):
                    if error:
                        if errType == MovementFailError.CANT_REACH_DEST_CELL or errType == MovementFailError.MAPCHANGE_TIMEOUT:
                            AutoTrip().start(msg.dstMapId, 1, callback=onresp)
                        else:
                            KernelEventsManager().send(KernelEvent.ClientRestart, f"Follow transition failed for reason : {error}")
                ChangeMap().start(transition=msg.transition, dstMapId=msg.dstMapId, callback=onresp)
            return True
        
        return False

    def onTimeout(self, msg: RPCMessage, timeout):
        if msg.uid in self._waitingForResp:
            respw = self._waitingForResp[msg.uid]
            if "callback" in respw:
                self._waitingForResp.pop(msg.uid)
                respw["callback"](result=None, error=self.CALL_TIMEOUT, sender=threading.current_thread().name)
            if "event" in respw:
                respw["event"].set()
                respw["result"] = None
                respw["err"] = self.CALL_TIMEOUT

    def askForStatus(self, dst, callback):
        msg = GetStatusMessage(dst)
        self.send(msg, callback)

    def askForStatusSync(self, dst, timeout=20):
        msg = GetStatusMessage(dst)
        return self.sendSync(msg, timeout)

    def askCurrVertex(self, dst, callback):
        msg = GetCurrentVertexMessage(dst)
        self.send(msg, callback)

    def askCurrVertexSync(self, dst, timeout=20):
        msg = GetCurrentVertexMessage(dst)
        return self.sendSync(msg, timeout)

    def askMoveToVertex(self, dst, vertex):
        msg = MoveToVertexMessage(dst, vertex)
        self.send(msg)

    def askFollowTransition(self, dst, transition, dstMapId):
        msg = FollowTransitionMessage(dst, transition, dstMapId)
        self.send(msg)

    def askComeToCollect(self, dst, bankInfo, guestInfo, callback):
        msg = ComeToCollectMessage(dst, bankInfo, guestInfo)
        self.send(msg, callback)

    def send(self, msg: RPCMessage, callback=None, timeout=60) -> None:
        inst = Kernel.getInstance(msg.dest)
        if not inst:
            if callback:
                return callback(result=None, error=self.DEST_KERNEL_NOT_FOUND, sender=msg.sender)
        if not msg.oneway and msg.uid not in self._waitingForResp:
            self._waitingForResp[msg.uid] = {}
            self._waitingForResp[msg.uid]["timeout"] = BenchmarkTimer(timeout, self.onTimeout, [msg, timeout])
            self._waitingForResp[msg.uid]["callback"] = callback
            self._waitingForResp[msg.uid]["timeout"].start()
        inst.worker.process(msg)

    def sendSync(self, msg: RPCMessage, timeout=60) -> RPCResponseMessage:
        if msg.oneway:
            raise Exception("sendSync can't be used with oneway message")
        if msg.uid not in self._waitingForResp:
            self._waitingForResp[msg.uid] = {
                "timeout": BenchmarkTimer(timeout, self.onTimeout, [msg, None]),
                "event": threading.Event(),
            }
            self._waitingForResp[msg.uid]["timeout"].start()
        resw = self._waitingForResp[msg.uid]
        inst = Kernel.getInstance(msg.dest)
        inst.worker.process(msg)
        if not resw["event"].wait(10):
            raise TimeoutError(self.CALL_TIMEOUT)
        result = resw["result"]
        error = resw.get("err")
        self._waitingForResp.pop(msg.uid)
        if error:
            raise Exception(error)
        return result
