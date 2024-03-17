from pyd2bot.logic.managers.AccountManager import AccountManager
from pyd2bot.Pyd2Bot import Pyd2Bot
from pyd2bot.thriftServer.pyd2botService.ttypes import (Path, PathType,
                                                        Session, SessionType,
                                                        TransitionType,
                                                        UnloadType, Vertex)

# ankarnam 154010883
# village astrub 191106048
# ankama coin bouftou 88082704
# Lac cania - pleines rocheuses : 156240386

if __name__ == "__main__":
    account_key = "244588168098991483"
    creds = AccountManager.get_credentials(account_key)
    session = Session(
        id="test_fight_solo",
        character=creds['character'],
        unloadType=UnloadType.BANK,
        type=SessionType.FIGHT,
        path=Path(
            id="test_path",
            type=PathType.RandomSubAreaFarmPath,
            startVertex=Vertex(mapId=191106048.0, zoneId=1),
            transitionTypeWhitelist=[TransitionType.SCROLL, TransitionType.SCROLL_ACTION],
        ),
        monsterLvlCoefDiff=1.4,
        apikey=creds['apikey'],
        cert=creds['cert'],
    )
    bot = Pyd2Bot(session)
    bot.start()
    bot.join()
