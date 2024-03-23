import os

BASEDIR = os.path.dirname(os.path.abspath(__file__))
class BotConstants:
    PERSISTENCE_DIR = os.path.join(BASEDIR, "persistence")
    if not os.path.exists(PERSISTENCE_DIR):
        os.makedirs(PERSISTENCE_DIR)
    KEYS_DIR = os.path.join(os.getenv("APPDATA"), "pyd2bot", "secrects", "vault")
