"""
BOM_Explosion.py

Core logic for the BOM Explosion tool.

Responsibilities:
- Handle upload of BOM data (CSV/Excel/etc.).
- Parse uploaded data into an internal representation.
- Prepare a "Topology" view (graph-like structure) once data are loaded.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


# ---------- Data Models ----------

@dataclass
class BOMItem:
    """Represents a single line in the BOM."""
    parent: str
    child: str
    quantity: float = 1.0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BOMTopology:
    """
    Internal representation of the BOM topology.

    This can later be rendered as:
    - a graph (networkx, pyvis, etc.),
    - a tree table,
    - or any visual you like in the "Topology" tab.
    """
    nodes: List[str] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)  # e.g. {"from": parent, "to": child, "qty": 2}


# ---------- Core Parsing Logic ----------

def parse_bom_dataframe(df) -> List[BOMItem]:
    """
    Convert a tabular BOM (e.g. pandas DataFrame) into a list of BOMItem.

    Expected minimal columns:
    - 'Parent'
    - 'Child'
    Optionally:
    - 'Quantity' (defaults to 1 if missing)
    - any other columns stored in BOMItem.extra

    Parameters
    ----------
    df : pandas.DataFrame
        Dataframe containing BOM data.

    Returns
    -------
    List[BOMItem]
    """
    required_cols = {"Parent", "Child"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in BOM data: {missing}")

    bom_items: List[BOMItem] = []
    for _, row in df.iterrows():
        parent = str(row["Parent"])
        child = str(row["Child"])
        quantity = float(row.get("Quantity", 1))

        # Everything else goes into 'extra'
        extra = {
            col: row[col]
            for col in df.columns
            if col not in {"Parent", "Child", "Quantity"}
        }

        bom_items.append(BOMItem(parent=parent, child=child, quantity=quantity, extra=extra))

    return bom_items


def build_topology(bom_items: List[BOMItem]) -> BOMTopology:
    """
    Build a topology object from BOM items.

    This is the backbone of the "Topology" tab: once the BOM is loaded and parsed,
    we construct a graph-like representation that the UI can render.

    Parameters
    ----------
    bom_items : List[BOMItem]

    Returns
    -------
    BOMTopology
    """
    nodes_set = set()
    edges: List[Dict[str, Any]] = []

    for item in bom_items:
        nodes_set.add(item.parent)
        nodes_set.add(item.child)

        edges.append(
            {
                "from": item.parent,
                "to": item.child,
                "quantity": item.quantity,
                "meta": item.extra,
            }
        )

    return BOMTopology(nodes=sorted(nodes_set), edges=edges)


# ---------- UI Facade (to be wired to Streamlit) ----------

class BOMExplosionApp:
    """
    Facade around the core logic, so Streamlit (or other UIs)
    can call simple methods.

    The UI "Topology" tab can:
    - Check if topology is available.
    - Retrieve nodes/edges and render them.
    """

    def __init__(self):
        self._bom_items: Optional[List[BOMItem]] = None
        self._topology: Optional[BOMTopology] = None
        self._raw_df = None  # Optional: keep original DataFrame for data tab

    # --- Upload / Load ---

    def load_from_dataframe(self, df) -> None:
        """
        Called by the UI after the user uploads a file
        and it has been read into a pandas.DataFrame.
        """
        self._raw_df = df
        self._bom_items = parse_bom_dataframe(df)
        self._topology = build_topology(self._bom_items)

    def has_data(self) -> bool:
        """Return True if BOM data has been loaded."""
        return self._bom_items is not None

    def has_topology(self) -> bool:
        """Return True if topology is ready."""
        return self._topology is not None

    # --- Accessors ---

    def get_dataframe(self):
        """Return the original DataFrame, if stored."""
        return self._raw_df

    def get_topology(self) -> Optional[BOMTopology]:
        """Return the computed topology (or None if not available)."""
        return self._topology

    def get_nodes(self) -> List[str]:
        return self._topology.nodes if self._topology else []

    def get_edges(self) -> List[Dict[str, Any]]:
        return self._topology.edges if self._topology else []
