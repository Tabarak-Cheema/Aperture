"""Catalog and semantic-layer package.

Stores tables, columns, profiles and relationships. Exposes an entity linker
(fuzzy + phonetic + distinct-value index) that maps user tokens to columns and
values without calling the model.
"""

from catalog.models import Catalog, Column, Relationship, Table, TableProfile
from catalog.semantic import DimensionYAML, MetricYAML, SemanticLayer, load_semantic_yaml
from catalog.synonyms import SynonymIndex

__all__ = [
    "Catalog",
    "Column",
    "DimensionYAML",
    "MetricYAML",
    "Relationship",
    "SemanticLayer",
    "SynonymIndex",
    "Table",
    "TableProfile",
    "load_semantic_yaml",
]
