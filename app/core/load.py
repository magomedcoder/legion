import importlib
import os
import sys
import traceback

from os import listdir
from os.path import isfile, isdir, join

"""
    Класс загрузчика расширений

    Формат расширения: app/extensions/<extension_name>/main.py

    Каждое расширение должно реализовывать:
        start(loader) -> dict (манифест)
        (опционально) start_with_options(loader, manifest) -> dict | None - вызывается после того, как manifest["options"] заполнен значениями
"""
class Load:
    def __init__(self):
        app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.extension_manifests = {}
        self.extensions_root = os.path.join(app_dir, "extensions")
        self.show_traceback_on_extension_errors = False

    """
        Загружает все расширения из папок с main.py: app/extensions/<extension_name>/main.py
    """
    def init_extensions(self, list_first_extensions=[]):
        self.extension_manifests = {}

        for name in list_first_extensions:
            self.init_extension(name)

        try:
            entries = listdir(self.extensions_root)
        except FileNotFoundError:
            print(f"ПРЕДУПРЕЖДЕНИЕ: папка с расширениями не найдена: {self.extensions_root}", file=sys.stderr)
            entries = []

        for name in entries:
            extension_dir = join(self.extensions_root, name)
            if isdir(extension_dir) and isfile(join(extension_dir, "main.py")) and name not in self.extension_manifests:
                self.init_extension(name)

    """
        Загружает одно расширение по имени папки: app/extensions/<folder_name>/main.py
    """
    def init_extension(self, folder_name: str):
        module_path = f"app.extensions.{folder_name}.main"

        try:
            mod = self.import_extension(module_path)
        except Exception as e:
            self.print_error(f"ОШИБКА: {folder_name} - ошибка импорта: {e}")
            return False

        try:
            manifest = mod.start(self)
            if not isinstance(manifest, dict):
                raise TypeError("start() должен возвращать dict (манифест)")
        except Exception as e:
            self.print_error(f"ОШИБКА: {folder_name} - ошибка в start(): {e}")
            return False

        if "options" in manifest and not isinstance(manifest["options"], dict):
            self.print_error(f"ОШИБКА: {folder_name} - 'options' в манифесте должен быть dict")
            return False
        manifest.setdefault("options", {})

        try:
            if hasattr(mod, "start_with_options"):
                res2 = mod.start_with_options(self, manifest)
                if isinstance(res2, dict):
                    manifest = res2
                    if "options" in manifest and not isinstance(manifest["options"], dict):
                        self.print_error(f"ОШИБКА: {folder_name} - 'options' после start_with_options должен быть dict")
                        return False
                    manifest.setdefault("options", {})
        except Exception as e:
            self.print_error(f"ОШИБКА: {folder_name} - ошибка в start_with_options(): {e}")
            return False

        try:
            self.process_extension_manifest(folder_name, manifest)
        except Exception as e:
            self.print_error(f"ОШИБКА: {folder_name} - ошибка обработки манифеста: {e}")
            return False

        self.extension_manifests[folder_name] = manifest
        return True

    """
        Печатает сообщение об ошибке.
        Если self.show_traceback_on_extension_errors=True - дополнительно печатает трейсбек
    """
    def print_error(self, msg: str):
        print(msg, file=sys.stderr)
        if self.show_traceback_on_extension_errors:
            traceback.print_exc()

    """
        Импортирует расширение по полному имени
    """
    def import_extension(self, module_name: str):
        return importlib.import_module(module_name)

    """
        Обработка манифеста расширения (переопределяйте в наследнике при необходимости)
    """
    def process_extension_manifest(self, folder_name: str, manifest: dict):
        print(f"РАСШИРЕНИЕ ЗАГРУЖЕНО: {folder_name} - манифест обработан")
        return

    """
        Возвращает манифест указанного расширения
    """
    def extension_manifest(self, extension_name):
        return self.extension_manifests.get(extension_name, {})

    """
        Возвращает опции указанного расширения
    """
    def extension_options(self, extension_name):
        manifest = self.extension_manifest(extension_name)
        return manifest.get("options")
