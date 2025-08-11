```bash
sudo apt install software-properties-common cmake pkg-config python3-launchpadlib python3-pip libcairo2-dev libgirepository-2.0-dev
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install cmake pkg-config python3 python3-venv python3-dev python3-tk
```

```bash
wget -O app/lib/eng_to_ipa.zip https://github.com/mphilli/English-to-IPA/archive/refs/heads/master.zip

unzip -o app/lib/eng_to_ipa.zip -d app/lib

mv app/lib/English-to-IPA-master app/lib/eng_to_ipa

rm app/lib/eng_to_ipa.zip
```

```bash
wget -O app/models/vosk-model-small-ru-0.22.zip https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip

unzip -o app/models/vosk-model-small-ru-0.22.zip -d app/models

mv app/models/vosk-model-small-ru-0.22 app/models/vosk

rm app/models/vosk-model-small-ru-0.22.zip
```

```bash
python3 -m venv .venv

source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
pip install PyGObject

cd app/lib && pip install -e . && cd ../..

python3 main.py --mode mic
python3 main.py --mode api
```