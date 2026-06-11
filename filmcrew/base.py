import os
import re

import yaml

_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _expand_env(obj):
    """Recursively expand ${VAR} in config strings from the environment.

    Unset vars become "" (not the literal ${VAR}) so that `if not api_key`
    graceful-degradation checks fire correctly. Only the LLM client used to
    expand env vars; the media APIs read api_key literally — so without this
    they received the string "${REPLICATE_API_KEY}" and 401'd. (2026-06-11.)
    """
    if isinstance(obj, dict):
        return {k: _expand_env(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env(v) for v in obj]
    if isinstance(obj, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), obj)
    return obj


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
        return _expand_env(yaml.safe_load(f))


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
