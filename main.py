if __name__ == "__main__":
    from pyd2bot.PyD2Bot import PyD2Bot
    from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", help="the server host", type=str, default="0.0.0.0")
    parser.add_argument("--port", help="the server port", type=int, default=9999)
    parser.add_argument("--id", help="the server id", type=str, default="unknown")
    args = parser.parse_args()
    Logger.prefix = args.id
    PyD2Bot(args.id, args.host, args.port).runHttpServer()
