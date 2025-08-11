import importlib
import os
import sys
import traceback

from os import listdir
from os.path import isfile, isdir, join

"""
    Класс загрузчика плагинов

    Формат плагина: app/plugins/<plugin_name>/main.py

    Каждый плагин должен содержать:
        start(loader) -> dict (манифест)
        опционально: start_with_options(loader, manifest) -> dict | None - вызывается уже после установки manifest["options"]
"""

class Load:
    def __init__(self):
        app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.plugin_manifests = {}
        self.plugins_root = os.path.join(app_dir, "plugins")
        self.showTracebackOnPluginErrors = False

    """
        Загружает все плагины из папок с main.py: app/plugins/<plugin_name>/main.py
        list_first_plugins- список плагинов (имена папок), которые нужно загрузить первыми
    """
    def init_plugins(self, list_first_plugins=None):
        if list_first_plugins is None:
            list_first_plugins = []

        self.plugin_manifests = {}

        for name in list_first_plugins:
            self.init_plugin(name)

        try:
            entries = listdir(self.plugins_root)
        except FileNotFoundError:
            print(f"ПРЕДУПРЕЖДЕНИЕ: папка с плагинами не найдена: {self.plugins_root}", file=sys.stderr)
            entries = []

        for name in entries:
            plugin_dir = join(self.plugins_root, name)
            if isdir(plugin_dir) and isfile(join(plugin_dir, "main.py")) and name not in self.plugin_manifests:
                self.init_plugin(name)

    """
        Загружает один плагин по имени папки - app/plugins/<folder_name>/main.py
    """
    def init_plugin(self, folder_name: str):
        module_path = f"app.plugins.{folder_name}.main"

        try:
            mod = self.import_plugin(module_path)
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
            self.process_plugin_manifest(folder_name, manifest)
        except Exception as e:
            self.print_error(f"ОШИБКА: {folder_name} - ошибка обработки манифеста: {e}")
            return False

        self.plugin_manifests[folder_name] = manifest
        return True

    """
        Печатает сообщение об ошибке
        Если self.showTracebackOnPluginErrors=True - дополнительно печатает трейсбек
    """
    def print_error(self, msg: str):
        print(msg, file=sys.stderr)
        if self.showTracebackOnPluginErrors:
            traceback.print_exc()

    """
        Импортирует модуль по полному имени
    """
    def import_plugin(self, module_name: str):
        return importlib.import_module(module_name)

    """
        Обработка манифеста плагина (переопределяйте в наследнике при необходимости)
    """
    def process_plugin_manifest(self, folder_name: str, manifest: dict):
        print(f"ПЛАГИН ЗАГРУЖЕН: {folder_name} - манифест обработан")
        return

    """
        Возвращает манифест указанного плагина
    """
    def plugin_manifest(self, pluginname):
        return self.plugin_manifests.get(pluginname, {})

    """
        Возвращает опции указанного плагина
    """
    def plugin_options(self, pluginname):
        manifest = self.plugin_manifest(pluginname)
        return manifest.get("options")
