import copy
import json
import os

from util.paths import DEFAULT_CONFIG_PATH, CONFIG_PATH
from util.input_constants import scancode_config_name, scancode_from_config


class ConfigNode:
    def __repr__(self):
        return repr(self.__dict__)


class ConfigManager:
    def __init__(self):
        self.defaults = {}
        self.revision = 0
        self.reload()

    def deep_merge(self, base, updates):
        for key, value in updates.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self.deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    def strip_unknown(self, current, defaults):
        """Removes any keys from 'current' that do not exist in 'defaults'."""
        cleaned = {}
        for k, v in current.items():
            if k not in defaults:
                continue
            if isinstance(v, dict) and isinstance(defaults[k], dict):
                nested_clean = self.strip_unknown(v, defaults[k])
                if nested_clean:
                    cleaned[k] = nested_clean
            else:
                cleaned[k] = v
        return cleaned

    def strip_defaults(self, current, defaults):
        """Removes any keys from 'current' that are identical to 'defaults'."""
        cleaned = {}
        for k, v in current.items():
            if k not in defaults:
                cleaned[k] = v
                continue
            if isinstance(v, dict) and isinstance(defaults[k], dict):
                nested_clean = self.strip_defaults(v, defaults[k])
                if nested_clean:
                    cleaned[k] = nested_clean
            else:
                if v != defaults[k]:
                    cleaned[k] = v
        return cleaned

    def _load_raw_data(self):
        with open(DEFAULT_CONFIG_PATH) as f:
            self.defaults = json.load(f)

        overrides = {}
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                try:
                    overrides = json.load(f)
                except json.JSONDecodeError:
                    overrides = {}

        # Strip out old settings that no longer exist in the defaults
        clean_overrides = self.strip_unknown(overrides, self.defaults)

        return self.deep_merge(copy.deepcopy(self.defaults), clean_overrides)

    def _build_nodes(self, target_obj, data, current_path=""):
        for key, value in data.items():
            path_for_child = f"{current_path}.{key}" if current_path else key

            if isinstance(value, dict):
                if not hasattr(target_obj, key) or not isinstance(getattr(target_obj, key), ConfigNode):
                    setattr(target_obj, key, ConfigNode())

                self._build_nodes(getattr(target_obj, key), value, path_for_child)

            else:
                parent_node_name = current_path.split('.')[-1] if current_path else ""

                if parent_node_name == "keybinds":
                    value = scancode_from_config(value)

                setattr(target_obj, key, value)

    def reload(self):
        data = self._load_raw_data()
        self._build_nodes(self, data)
        self.revision += 1

    def get_default(self, path: str):
        keys = path.split('.')
        val = self.defaults
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return None

        if "keybinds" in keys and isinstance(val, str):
            val = scancode_from_config(val)

        return val

    def get(self, path: str):
        keys = path.split('.')
        node = self
        for key in keys:
            node = getattr(node, key)
        return node

    def save(self, changes):
        # Format keybinds back to strings
        if "keybinds" in changes:
            for action, key_int in changes["keybinds"].items():
                changes["keybinds"][action] = scancode_config_name(key_int)

        # Merge changes into the current active config data
        current_data = self._load_raw_data()
        updated_data = self.deep_merge(current_data, changes)

        # Strip everything that matches the default config
        to_save = self.strip_defaults(updated_data, self.defaults)

        with open(CONFIG_PATH, "w") as f:
            json.dump(to_save, f, indent=4)

        self.reload()


config = ConfigManager()


class ConfigChanges:
    def __init__(self):
        self.values = {}

    def clear(self):
        self.values = {}

    def get(self, path, default=None):
        keys = path.split('.')
        d = self.values
        for key in keys:
            if key not in d:
                return default
            d = d[key]
        return d

    def set(self, path, value):
        keys = path.split('.')
        d = self.values
        for key in keys[:-1]:
            if key not in d:
                d[key] = {}
            d = d[key]
        d[keys[-1]] = value

    def remove(self, path):
        keys = path.split('.')
        d = self.values
        for key in keys[:-1]:
            if key not in d:
                d[key] = {}
            d = d[key]
        del d[keys[-1]]

    def restore_all_defaults(self, defaults_dict=None, current_path=""):
        if defaults_dict is None:
            defaults_dict = config.defaults

        for k, v in defaults_dict.items():
            path = f"{current_path}.{k}" if current_path else k

            if isinstance(v, dict):
                self.restore_all_defaults(v, path)
            else:
                if current_path == "keybinds":
                    val = scancode_from_config(v)
                    if isinstance(val, int):
                        self.set(path, val)
                else:
                    self.set(path, v)
