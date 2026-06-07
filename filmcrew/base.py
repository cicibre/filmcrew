import os

import yaml


def _config_path():
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "config.yaml"),
        "config.yaml",
        "/Users/cc/filmcrew/config.yaml",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)
    raise FileNotFoundError("config.yaml not found")


def load_config(path=None):
    if path is None:
        path = _config_path()
    with open(path, "r") as f:
        return yaml.safe_load(f)


class BaseCrewMember:
    role = "base"

    def __init__(self, config):
        self.config = config
        self.mode = config.get("general", {}).get("mode", "dry_run")

    def work(self, job, manifest):
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement work()"
        )

    def _is_dry_run(self):
        return self.mode == "dry_run"
