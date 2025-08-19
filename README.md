```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install software-properties-common cmake pkg-config python3-launchpadlib python3-pip cmake pkg-config python3 python3-venv python3-dev python3-tk libcairo2-dev libgirepository1.0-dev portaudio19-dev rhvoice rhvoice-russian librhvoice-dev
```

```bash
python3 -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

cd app/lib && pip install -e . && cd ../..

python3 main.py --mode mic
python3 main.py --mode api
```