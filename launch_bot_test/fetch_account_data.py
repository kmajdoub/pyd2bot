
from pyd2bot.logic.managers.AccountManager import AccountManager

account_key = "your_account_key"
game = 1 # 1 = Dofus
apikey = 'your_api_key'
certificate_id =  'your_certificate_id'
certificate_hash = "your_certificate_hash"
account_data = AccountManager.fetch_account(game, apikey, int(certificate_id), certificate_hash)
print(account_data)