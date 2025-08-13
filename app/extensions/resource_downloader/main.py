import os
import shutil
import zipfile
import urllib.request
from typing import Dict, Any
from app.core.core import Core

"""
    Загрузчик ресурсов

    Опции:
        auto_download_on_start : bool - автоматически скачивать при старте, если ресурсы отсутствуют
        force_on_start         : bool - принудительно перекачивать при старте, даже если ресурс уже установлен
        resources              : dict - список ресурсов: имя -> конфигурация
            {
                "<имя_ресурса>": {
                    "url": "<ссылка на ZIP>",
                    "zip_path": "<куда скачать ZIP>",
                    "extract_to": "<куда распаковать>",
                    "src_dir": "<имя распакованной папки>",
                    "dest_dir": "<куда переместить>"
                }
            }
"""

modname = os.path.basename(__package__)[12:]

def start(core: Core):
    manifest = {
        "name": "Загрузчик ресурсов",

        "options": {
            "auto_download_on_start": True,
            "force_on_start": False,
            "resources": {
                "eng_to_ipa": {
                    "url": "https://github.com/mphilli/English-to-IPA/archive/refs/heads/master.zip",
                    "zip_path": "runtime/resource-downloader/lib/eng_to_ipa.zip",
                    "extract_to": "runtime/resource-downloader/lib",
                    "src_dir": "runtime/resource-downloader/lib/English-to-IPA-master",
                    "dest_dir": "app/lib/eng_to_ipa"
                },
                "vosk_ru_small": {
                    "url": "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip",
                    "zip_path": "runtime/resource-downloader/models/vosk-model-small-ru-0.22.zip",
                    "extract_to": "runtime/resource-downloader/models",
                    "src_dir": "runtime/resource-downloader/models/vosk-model-small-ru-0.22",
                    "dest_dir": "app/models/vosk"
                },
                "mobilenet_ssd": {
                    "url": "https://github.com/chuanqi305/MobileNet-SSD/archive/refs/heads/master.zip",
                    "zip_path": "runtime/resource-downloader/models/MobileNet-SSD.zip",
                    "extract_to": "runtime/resource-downloader/models",
                    "src_dir": "runtime/resource-downloader/models/MobileNet-SSD-master",
                    "dest_dir": "app/models/mobilenet-ssd"
                }
            }
        }
    }

    opts = _get_opts(core, modname, manifest["options"])

    if opts.get("auto_download_on_start", True):
        force = bool(opts.get("force_on_start", False))
        resources: Dict[str, Dict[str, str]] = opts.get("resources", {})
        for name, cfg in resources.items():
            try:
                _ensure_resource(cfg, force, tag=f"[{name}]")
            except Exception as e:
                core.print_red(f"[Загрузчик ресурсов] Ошибка при скачивании {name}: {e}")

    return manifest

def start_with_options(core: Core, manifest: dict):
    return manifest

def _get_opts(core, extension_name: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
    saved = core.extension_options(extension_name) or {}
    return {**defaults, **saved}

"""
    Проверка и загрузка ресурса
"""
def _ensure_resource(cfg: Dict[str, str], force: bool, tag: str):
    url = cfg["url"]
    zip_path = cfg["zip_path"]
    extract_to = cfg["extract_to"]
    src_dir = cfg["src_dir"]
    dest_dir = cfg["dest_dir"]

    if os.path.isdir(dest_dir):
        if not force:
            # print(f"{tag} Ресурс уже установлен: {dest_dir}")
            return
        print(f"{tag} Принудительное обновление ресурса...")
        shutil.rmtree(dest_dir, ignore_errors=True)

    os.makedirs(extract_to, exist_ok=True)

    print(f"{tag} Скачивание: {url}")
    _download(url, zip_path)

    print(f"{tag} Распаковка: {zip_path} -> {extract_to}")
    _unzip(zip_path, extract_to)

    if os.path.isdir(dest_dir):
        shutil.rmtree(dest_dir, ignore_errors=True)

    if os.path.isdir(src_dir):
        os.rename(src_dir, dest_dir)
    else:
        raise RuntimeError(f"{tag} Не найдена распакованная папка: {src_dir}")

    _safe_remove(zip_path)
    print(f"{tag} Установка завершена: {dest_dir}")

def _download(url: str, dst_zip: str):
    urllib.request.urlretrieve(url, dst_zip)
    if not os.path.isfile(dst_zip) or os.path.getsize(dst_zip) == 0:
        raise RuntimeError(f"Файл не скачан или пуст: {dst_zip}")

def _unzip(zip_path: str, extract_to: str):
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)

def _safe_remove(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
