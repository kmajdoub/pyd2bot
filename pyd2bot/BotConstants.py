import os

BASEDIR = os.path.dirname(os.path.abspath(__file__))
class BotConstants:
    PERSISTENCE_DIR = os.path.join(os.getenv("APPDATA"), "pyd2bot", "persistence")
    KEYS_DIR = os.path.join(os.getenv("APPDATA"), "pyd2bot", "secrects", "vault")
    
    if not os.path.exists(PERSISTENCE_DIR):
        os.makedirs(PERSISTENCE_DIR)
    
    if not os.path.exists(KEYS_DIR):
        os.makedirs(KEYS_DIR)
