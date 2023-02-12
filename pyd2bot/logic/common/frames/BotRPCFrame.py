import threading
from pyd2bot.apis.PlayerAPI import PlayerAPI
from pyd2bot.logic.common.rpcMessages.ComeToCollectMessage import ComeToCollectMessage
from pyd2bot.logic.common.rpcMessages.FollowTransitionMessage import FollowTransitionMessage
from pyd2bot.logic.common.rpcMessages.GetCurrentVertexMessage import GetCurrentVertexMessage
from pyd2bot.logic.common.rpcMessages.GetStatusMessage import GetStatusMessage
from pyd2bot.logic.common.rpcMessages.MoveToVertexMessage import MoveToVertexMessage
from pyd2bot.logic.common.rpcMessages.RCPResponseMessage import RPCResponseMessage
from pyd2bot.logic.common.rpcMessages.RPCMessage import RPCMessage
from pyd2bot.logic.roleplay.frames.BotSellerCollectFrame import BotSellerCollectFrame
from pyd2bot.logic.roleplay.messages.LeaderPosMessage import LeaderPosMessage
from pyd2bot.logic.roleplay.messages.LeaderTransitionMessage import LeaderTransitionMessage
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldPathFinder import WorldPathFinder
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority


class BotRPCFrame(Frame):
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
                rsp = RPCResponseMessage(msg, data=PlayerAPI().status)
                self.send(rsp)
                return True

            elif isinstance(msg, GetCurrentVertexMessage):
                rsp = RPCResponseMessage(msg, data=WorldPathFinder().currPlayerVertex)
                self.send(rsp)
                return True

            elif isinstance(msg, MoveToVertexMessage):
                Kernel().worker.process(LeaderPosMessage(msg.vertex))
                return True

            elif isinstance(msg, FollowTransitionMessage):
                Kernel().worker.process(LeaderTransitionMessage(msg.transition))
                return True

            elif isinstance(msg, ComeToCollectMessage):
                Kernel().worker.addFrame(BotSellerCollectFrame(msg.bankInfos, msg.guestInfos))
                return True

        return False

    def onTimeout(self, msg: RPCMessage, timeout):
        ConnectionsHandler.removeListener(msg.dest, lambda: self.send(msg, None, timeout))
        if msg.uid in self._waitingForResp:
            respw = self._waitingForResp[msg.uid]
            if "callback" in respw:
                self._waitingForResp.pop(msg.uid)
                respw["callback"](result=None, error="call timeout")
            if "event" in respw:
                respw["event"].set()
                respw["result"] = None
                respw["err"] = "RPC call timeout"

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

    def askFollowTransition(self, dst, transition):
        msg = FollowTransitionMessage(dst, transition)
        self.send(msg)

    def askComeToCollect(self, dst, bankInfo, guestInfo):
        msg = ComeToCollectMessage(dst, bankInfo, guestInfo)
        self.send(msg)

    def send(self, msg: RPCMessage, callback=None, timeout=20) -> None:
        inst = Kernel.getInstance(msg.dest)
        if not inst:
            return
        if not msg.oneway and msg.uid not in self._waitingForResp:
            self._waitingForResp[msg.uid] = {}
            self._waitingForResp[msg.uid]["timeout"] = BenchmarkTimer(timeout, self.onTimeout, [msg, timeout])
            self._waitingForResp[msg.uid]["callback"] = callback
            self._waitingForResp[msg.uid]["timeout"].start()
        inst.worker.process(msg)

    def sendSync(self, msg: RPCMessage, timeout=20) -> RPCResponseMessage:
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
            raise TimeoutError("RPC call timeout")
        result = resw["result"]
        error = resw.get("err")
        self._waitingForResp.pop(msg.uid)
        if error:
            raise Exception(error)
        return result
