from __future__ import annotations

import abc
from typing import Dict, List, Optional, Type

from .setup_step import SetupStep


class PlatformInstall(SetupStep):
    """Base class and registry for composite SetupSteps, PlatformInstalls"""

    __registry: Dict[str, Type[PlatformInstall]] = {}

    @classmethod
    @abc.abstractmethod
    def get_key(cls) -> str:
        """Gets the key of the platform.

        This is the same key that gets displayed in the selection menu and is
        used with the `--platform` command line argument.
        """
        pass

    @classmethod
    def from_key(cls, platform_key: str) -> Optional[PlatformInstall]:
        """Constructs a Platform subclass that has been registered"""
        subclass = cls.__registry.get(platform_key)
        if subclass is None:
            return None
        else:
            return subclass()

    @classmethod
    def platforms(cls) -> List[str]:
        """Returns the list of keys that are registered"""
        return list(cls.__registry.keys())

    @classmethod
    def register(cls, subclass: Type[PlatformInstall]) -> Type[PlatformInstall]:
        """Registers a subclass"""
        assert issubclass(subclass, cls)
        cls.__registry[subclass.get_key()] = subclass
        return subclass
