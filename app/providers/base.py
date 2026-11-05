from abc import ABC, abstractmethod
from typing import List, Dict, Any
from app.database.models import CarListing

class BaseCarProvider(ABC):
    def __init__(self, name: str, priority: int = 10):
        self.name = name
        self.priority = priority

    @abstractmethod
    def search(self, config: Dict[str, Any]) -> List[CarListing]:
        pass