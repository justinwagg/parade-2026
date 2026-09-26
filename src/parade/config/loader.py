import yaml
from pathlib import Path
from .models import Config


def load_config(path: Path) -> Config:
    """Load and validate YAML config. Raises ValidationError on bad config."""
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return Config.model_validate(data)


def load_fixture_profiles(profiles_dir: Path) -> dict:
    """Load all fixture profile YAML files from a directory tree.
    Returns dict[profile_id, profile_dict]."""
    profiles = {}
    for yaml_file in sorted(profiles_dir.rglob("*.yaml")):
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        if isinstance(data, list):
            for profile in data:
                profiles[profile["id"]] = profile
        elif isinstance(data, dict):
            profiles[data["id"]] = data
    return profiles


def load_cues(cues_dir: Path) -> list[dict]:
    """Load all cue definition YAML files."""
    cues = []
    if not cues_dir.exists():
        return cues
    for yaml_file in sorted(cues_dir.rglob("*.yaml")):
        with open(yaml_file) as f:
            data = yaml.safe_load(f) or []
        if isinstance(data, list):
            cues.extend(data)
        elif isinstance(data, dict):
            cues.append(data)
    return cues


def load_scenes(scenes_path: Path) -> list[dict]:
    """Load scene definitions from a YAML file."""
    if not scenes_path.exists():
        return []
    with open(scenes_path) as f:
        data = yaml.safe_load(f) or []
    return data if isinstance(data, list) else [data]
