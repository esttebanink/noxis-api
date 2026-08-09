from abc import ABC, abstractmethod
from typing import Any


class BaseEnricher(ABC):
    """
    Interfaz base para enrichers de NOXIS.
    """

    service_name: str = ""

    @abstractmethod
    async def enrich(
        self,
        username: str,
        result: dict[str, Any]
    ) -> dict[str, Any]:
        raise NotImplementedError
