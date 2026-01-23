"""
BOM_Explosion.py

Core logic for the BOM Explosion tool.

Parser expects an indented BOM with:
- 'Level'
- 'Component number'
and a quantity column like 'Comp. Qty (BUn)'.
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


# ---------- Core Parsing Logic (NOW: Level / Component number) ----------

def parse_bom_dataframe(df) -> List[BOMItem]:
    """
    Parse an indented BOM where hierarchy is given by 'Level' and components
    by 'Component number'.

    Assumptions:
    - Column 'Level' is numeric (1,2,3,...) representing indentation.
    - Column 'Component number' is the node identifier (string).
    - Column 'Comp. Qty (BUn)' (or similar) contains quantity per parent.

    Parent-finding rule:
    - For a row at level L (L > 1), its parent is the closest previous row
      with Level < L.
    - For Level 1:
        - The first Level 1 row is treated as the global root (no parent edge).
        - Additional Level 1 rows are children of that root.
    """
    required_cols = {"Level", "Component number"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in BOM data: {missing}")

    # Work on a copy and ensure Level is integer
    df = df.copy()
    df["Level"] = df["Level"].astype(int)

    # Detect a quantity column
    qty_col = None
    for cand in ["Comp. Qty (BUn)", "Comp. Qty", "Quantity"]:
        if cand in df.columns:
            qty_col = cand
            break

    bom_items: List[BOMItem] = []

    # Stack of ancestors: list of dicts {"level": int, "comp": str}
    stack: List[Dict[str, Any]] = []

    root_label: Optional[str] = None

    for _, row in df.iterrows():
        level = int(row["Level"])
        comp = str(row["Component number"])

        # Quantity: from qty_col or default 1
        if qty_col is not None:
            raw_qty = row[qty_col]
            try:
                # Handle European decimal "," if present
                quantity = float(str(raw_qty).replace(",", "."))
            except Exception:
                quantity = 1.0
        else:
            quantity = 1.0

        # Everything else goes into 'extra'
        extra = {
            col: row[col]
            for col in df.columns
            if col not in {"Level", "Component number"}
        }

        if level == 1:
            # First Level 1 is the root of the explosion
            if root_label is None:
                root_label = comp
                stack = [{"level": level, "comp": comp}]
                # No parent edge for the true root
                continue
            else:
                # Other Level 1 rows: treat them as direct children of the root
                parent = root_label
                bom_items.append(
                    BOMItem(parent=parent, child=comp, quantity=quantity, extra=extra)
                )
                stack = [{"level": level, "comp": comp}]
                continue

        # For level > 1, find the parent as closest previous with lower level
        while stack and stack[-1]["level"] >= level:
            stack.pop()

        if not stack:
            # Fallback: attach to root if stack got emptied
            parent = root_label if root_label is not None else "ROOT"
        else:
            parent = stack[-1]["comp"]

        bom_items.append(
            BOMItem(parent=parent, child=comp, quantity=quantity, extra=extra)
        )

        # Push current node to stack as potential parent for deeper levels
        stack.append({"level": level, "comp": comp})

    return bom_items


def build_topology(bom_items: List[BOMItem]) -> BOMTopology:
    """
    Build a topology object from BOM items.
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
        Uses the Level/Component-number-based parser.
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
