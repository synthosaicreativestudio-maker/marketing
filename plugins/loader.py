"""Plugin loader: imports modules from plugins/ and registers them based on config."""
import importlib
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def load_plugins(dispatcher, bot, config_path=None):
    config_path = config_path or Path('config/plugins.json')
    plugins = []
    try:
        cfg = json.loads(Path(config_path).read_text())
    except Exception:
        cfg = {}

    enabled = cfg.get('enabled', []) if isinstance(cfg, dict) else []

    # scan plugins directory
    for p in Path('plugins').glob('*.py'):
        name = p.stem
        if name == '__init__' or name.startswith('_'):
            continue
        try:
            mod = importlib.import_module(f'plugins.{name}')
            if enabled and name not in enabled:
                log.info('Plugin %s is disabled in config', name)
                continue
            if hasattr(mod, 'register'):
                handle = mod.register(dispatcher, bot, cfg.get('settings', {}))
                plugins.append(handle)
                log.info('Loaded plugin %s', name)
        except Exception as e:
            log.exception('Failed to load plugin %s: %s', name, e)

    return plugins
