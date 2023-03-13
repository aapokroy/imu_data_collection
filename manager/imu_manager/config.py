import yaml
from typing import Any, Dict, List, Mapping, Sequence


class FromMapping:
    """Class for converting from a mapping to a python object"""

    @staticmethod
    def __is_correct_mapping(mapping: Mapping) -> bool:
        """Check if all mapping keys are strings"""
        return all(map(lambda x: isinstance(x, str), mapping.keys()))

    def __init__(self, mapping: Mapping[str, Any],
                 keep_type: List[str] = []):
        for key, value in mapping.items():
            if key in keep_type:
                setattr(self, key, value)
                continue
            if isinstance(value, Mapping) and self.__is_correct_mapping(value):
                value = FromMapping(value, keep_type)
            elif isinstance(value, Sequence):
                for i, x in enumerate(value):
                    if isinstance(x, Mapping) and self.__is_correct_mapping(x):
                        value[i] = FromMapping(x, keep_type)
            setattr(self, key, value)

    def to_dict(self) -> Dict[str, Any]:
        """Convert object to a dictionary"""
        return {
            key: value.to_dict()
            if isinstance(value, FromMapping) else value
            for key, value in self.__dict__.items()
        }


class Config(FromMapping):
    """
    Config class for loading and saving yaml config files.
    Automatically converts yaml's dictionary structure to python object.
    """

    def __init__(self, path: str, keep_type: List[str] = []):
        self.config_path = path
        with open(path, 'r') as f:
            cfg = yaml.safe_load(f)
        super(Config, self).__init__(cfg, keep_type)

    def save(self):
        data = self.to_dict()
        if 'config_path' in data:
            del data['config_path']
        with open(self.config_path, 'w') as f:
            yaml.dump(data, f, sort_keys=False)
