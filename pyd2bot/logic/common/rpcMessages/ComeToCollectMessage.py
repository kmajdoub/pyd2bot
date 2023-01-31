from pyd2bot.logic.common.rpcMessages.RPCMessage import RPCMessage
from pyd2bot.misc.Localizer import BankInfos


class ComeToCollectMessage(RPCMessage):
    
    def __init__(self, dest, bankInfos: BankInfos, guestInfos: dict) -> None:
        super().__init__(dest)
        self.bankInfos = bankInfos
        self.guestInfos = guestInfos
        self.oneway = True