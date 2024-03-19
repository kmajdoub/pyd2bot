# Pyd2bot: A Python Bot for Dofus

Pyd2bot utilizes the Pydofus2 client as a background to automate tasks in Dofus. This guide is tailored for beginners, especially for Windows users.

## Join discord community

<https://discord.gg/kGeUTyTd>

## Prerequisites

- **Python 3.9.11**: Download and install from [python.org](https://www.python.org/downloads/release/python-3911/).
- **Pcap and Wireshark**: Required for sniffer functionality. Download Wireshark from [here](https://www.wireshark.org/download.html).

## Setup Steps for Developers

### 1. Setting Up the Environment

- **Create a New Folder**:
  - Open Command Prompt.
  - Create a new folder named `botdev` and navigate into it:

    ```bash
    mkdir botdev
    cd botdev
    ```

- **Clone Repositories**:
  - Clone the `pydofus2` repository inside botdev folder:

    ```bash
    git clone https://github.com/hadamrd/pydofus2.git
    ```

  - Clone the `pyd2bot` repository inside botdev folder:

    ```bash
    git clone https://github.com/hadamrd/pyd2bot.git
    ```

- **Create a Virtual Environment**:
  - Within the `botdev` folder, create a new fresh python virtual environement:

    ```bash
    python -m venv .venv
    ```

- **Intall repos for dev**:
  - Source the .venv `source .venv/Script/activate`
  - Navigate to the folder `pydofus2` and run `pip install -e`.
  - Navigate to the folder `pyd2bot` and run `pip install -e`.

### 2. Installing Dependencies

- **Activate Virtual Environment**:
  - Execute following command to activate the virtual env:

    ```bash
    source .venv\Scripts\activate
    ```

- **Install Dependencies**:
  - For `pyd2bot`:

    ```bash
    pip install -r pyd2bot/requirements.txt
    ```

  - For `pydofus2`:

    ```bash
    pip install -r pydofus2/requirements.txt
    ```

### 3. Configuration

- **Setup Config Files**:
  - In `pydofus2.pydofus2.com.ankamagames.dofus.Constants`, configure:
    - `DOFUS_ROOTDIR`: Path to your Dofus installation directory.
    - `LANG_FILE_PATH`: Path to your Dofus language file.
    - `LOGS_DIR`: Path to the folders you want pydofus2 to generate its logs to.
- **Edit Makefile for Dofus Protocol build tools**:
  - Modify the Makefile in `<pydofus2_dir>\pydofus2\devops\Makefile`.
  - Set variables like `DOFUSINVOKER`, `PYDOFUS_DIR`, etc.
    - Example:

      ```bash
      DOFUSINVOKER = D://Dofus//DofusInvoker.swf
      PYDOFUS_DIR = D://botdev//pydofus2
      PYD2BOT_DIR = D://botdev//pyd2bot
      VENV_DIR = D://botdev//.venv
      ```

### 4. Generate Keys and Unpack Maps

- Navigate to `<pydofus2_dir>\pydofus2\devops`.
- Execute:

```bash
make extract-keys
make unpack-maps
```

### 5. If you want to run the Sniffer App (Optional)

- Go to `<pydofus2_dir>\pydofus2\sniffer`.
- Install requirements and run the app:

```bash
pip install -r requirements.txt
python app.py
```

## Importing Account and Character Data

1. **Obtain Your HAAPI API Key**:

- Add your account to ankama launcher
- Clone launcherd2 projetct into your botdev folder : ```git clone https://github.com/hadamrd/launcherd2```
- Add its .pth file in the root of your .venv.
- Launch `python import_all_accounts_from_launcher.py`

2. **Configure and Run the treasure hunt farm Bot Example**:

- `cd launch_bot_test folder`
- Edit `run_treasureHuntBot.py`.
- Replace `account_key` with your account ID. The account ID is the key of the account in the `pyd2bot/persistence/accounts.json` file.
- Start the script to see the bot in action.

4. **Run example using the flask app**:

- `cd app`
- `python app.py`.

Follow these steps to successfully set up and run Pyd2bot on your Windows system.
