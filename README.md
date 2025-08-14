```bash
sudo apt install software-properties-common cmake pkg-config python3-launchpadlib python3-pip libcairo2-dev libgirepository-2.0-dev portaudio19-dev
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install cmake pkg-config python3 python3-venv python3-dev python3-tk
```

```bash
python3 -m venv .venv

source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
pip install PyGObject==3.40

cd app/lib && pip install -e . && cd ../..

python3 main.py --mode mic
python3 main.py --mode api
```