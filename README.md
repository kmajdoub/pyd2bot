# Pyd2bot: A Python Bot for Dofus 2

Pyd2bot utilizes the Pydofus2 client as a background to automate tasks in Dofus. This guide is tailored for beginners, especially for Windows users.

## Join discord community

<https://discord.gg/kGeUTyTd>

## Prerequisites

- **Python 3.9.11**: Download and install from [python.org](https://www.python.org/downloads/release/python-3911/).
- **Pcap and Wireshark**: Required for sniffer functionality. Download Wireshark from [here](https://www.wireshark.org/download.html).
- **Make**: Required for updating the protocol. You can install it with with chocolatery, ```shell choco install make```. If you dont have chocolatey install it.

## Setup Steps for Developers

### 1. Setting Up the Environment

- **Create a New Folder**:
  - Create a new folder named `botdev` and navigate into it:

    ```bash
    mkdir botdev
    cd botdev
    ```

- **Clone Repositories**:
  - Clone the `pydofus2` repository inside `botdev` folder:

    ```bash
    git clone https://github.com/hadamrd/pydofus2.git
    ```

  - Clone the `pyd2bot` repository inside `botdev` folder:

    ```bash
    git clone https://github.com/hadamrd/pyd2bot.git
    ```

- **Create a Virtual Environment**:
  - Within the `botdev` folder, create a new fresh python virtual environement:

    ```bash
    python -m venv .venv
    ```

### 2. Env variables configuration

Add the following env variables to your system:

- `DOFUS_HOME`: Path to your Dofus installation directory.
- `LOGS_DIR`: Path to the folder you want pydofus2 to generate its logs to.
- `PYBOTDEV_HOME`: Path to you `botdev` directory.

### 2. Installing Dependencies

```bash
source $PYBOTDEV_HOME/.venv/Script/activate
pip install -e $PYBOTDEV_HOME/pydofus2
pip install -e $PYBOTDEV_HOME/pyd2bot
```

### 4. Run Unpack Maps to dezip the game maps locally

```bash
cd $PYBOTDEV_HOME/pydofus2/updater
make unpack-maps
```

## To run the bot application

```bash
cd $PYBOTDEV_HOME/pydofus2/app
pip install -r requirements.txt
python app.py
```

### To run the Sniffer App (Optional)

```bash
cd $PYBOTDEV_HOME/pydofus2/sniffer
pip install -r requirements.txt
python app.py
```
