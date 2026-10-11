from typing import TYPE_CHECKING
from . import java
from atlas.metrics.adapters.kotlin import KotlinResolution
import atlas.metrics.adapters.go
from ...domain.models import Symbol
if TYPE_CHECKING:
    from . import python

def resolve():
    from .rust import RustResolution
