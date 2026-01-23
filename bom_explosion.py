"""
BOM (Bill of Materials) Explosion Tool

This tool displays the topology of all compounds and raw materials involved
in producing a single Finished Good SKU.
"""

from typing import Dict, List, Tuple, Set
from collections import defaultdict


class BOMExplosion:
    """
    A class to handle BOM explosion and display topology.
    """
    
    def __init__(self, bom_data: Dict[str, List[Tuple[str, float]]]):
        """
        Initialize the BOM explosion tool with BOM data.
        
        Args:
            bom_data: Dictionary mapping SKU to list of (component_sku, quantity) tuples
                     Example: {"FG001": [("COMP001", 2.0), ("RM001", 1.5)]}
        """
        self.bom_data = bom_data
        
    def explode(self, sku: str, quantity: float = 1.0, level: int = 0, 
                path: Set[str] = None) -> List[Tuple[int, str, float, str]]:
        """
        Recursively explode a SKU into all its components.
        
        Args:
            sku: The SKU to explode
            quantity: The quantity of this SKU needed
            level: Current depth level in the BOM tree
            path: Set of SKUs in the current path (to detect circular references)
        
        Returns:
            List of tuples: (level, sku, quantity, item_type)
        """
        if path is None:
            path = set()
        
        result = []
        
        # Check for circular reference in current path
        if sku in path:
            result.append((level, f"[CIRCULAR REFERENCE: {sku}]", quantity, "Error"))
            return result
        
        # Add to current path
        new_path = path | {sku}
        
        # Determine item type
        if sku not in self.bom_data or not self.bom_data[sku]:
            item_type = "Raw Material"
        elif level == 0:
            item_type = "Finished Good"
        else:
            item_type = "Compound"
        
        # Add current item
        result.append((level, sku, quantity, item_type))
        
        # Explode components if they exist
        if sku in self.bom_data:
            for component_sku, component_qty in self.bom_data[sku]:
                total_qty = quantity * component_qty
                component_result = self.explode(component_sku, total_qty, level + 1, new_path)
                result.extend(component_result)
        
        return result
    
    def display_topology(self, sku: str, quantity: float = 1.0) -> str:
        """
        Display the topology of a SKU in a tree-like format.
        
        Args:
            sku: The SKU to display
            quantity: The quantity of this SKU
        
        Returns:
            String representation of the BOM topology
        """
        explosion = self.explode(sku, quantity)
        
        lines = []
        lines.append("=" * 80)
        lines.append(f"BOM EXPLOSION FOR: {sku} (Quantity: {quantity})")
        lines.append("=" * 80)
        lines.append("")
        
        for level, item_sku, qty, item_type in explosion:
            indent = "  " * level
            prefix = "└─ " if level > 0 else ""
            lines.append(f"{indent}{prefix}{item_sku} (Qty: {qty:.2f}) [{item_type}]")
        
        lines.append("")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def get_summary(self, sku: str, quantity: float = 1.0) -> Dict[str, float]:
        """
        Get a summary of all raw materials needed for a SKU.
        
        Args:
            sku: The SKU to summarize
            quantity: The quantity of this SKU
        
        Returns:
            Dictionary mapping raw material SKU to total quantity needed
        """
        explosion = self.explode(sku, quantity)
        summary = defaultdict(float)
        
        for level, item_sku, qty, item_type in explosion:
            if item_type == "Raw Material":
                summary[item_sku] += qty
        
        return dict(summary)


def create_sample_bom_data() -> Dict[str, List[Tuple[str, float]]]:
    """
    Create sample BOM data for demonstration.
    
    Returns:
        Sample BOM data structure
    """
    return {
        # Finished Goods
        "FG001": [  # Widget A
            ("COMP001", 2.0),  # Frame Assembly
            ("COMP002", 1.0),  # Motor Assembly
            ("RM001", 4.0),    # Screws
        ],
        "FG002": [  # Widget B
            ("COMP001", 1.0),  # Frame Assembly
            ("COMP003", 2.0),  # Gear Assembly
            ("RM002", 0.5),    # Lubricant
        ],
        
        # Compounds
        "COMP001": [  # Frame Assembly
            ("RM003", 2.0),   # Steel Sheet
            ("RM004", 1.0),   # Paint
            ("RM001", 8.0),   # Screws
        ],
        "COMP002": [  # Motor Assembly
            ("RM005", 1.0),   # Motor
            ("RM006", 1.0),   # Wiring
            ("RM001", 4.0),   # Screws
        ],
        "COMP003": [  # Gear Assembly
            ("RM007", 2.0),   # Gear
            ("RM008", 1.0),   # Shaft
            ("RM002", 0.2),   # Lubricant
        ],
        
        # Raw Materials (no components)
        "RM001": [],  # Screws
        "RM002": [],  # Lubricant
        "RM003": [],  # Steel Sheet
        "RM004": [],  # Paint
        "RM005": [],  # Motor
        "RM006": [],  # Wiring
        "RM007": [],  # Gear
        "RM008": [],  # Shaft
    }


def main():
    """
    Main function to demonstrate BOM explosion tool.
    """
    # Create sample BOM data
    bom_data = create_sample_bom_data()
    
    # Initialize BOM explosion tool
    bom_tool = BOMExplosion(bom_data)
    
    # Example 1: Explode FG001
    print(bom_tool.display_topology("FG001", 1.0))
    
    # Example 2: Show raw materials summary
    print("\nRAW MATERIALS SUMMARY FOR FG001:")
    print("-" * 40)
    summary = bom_tool.get_summary("FG001", 1.0)
    for sku, qty in sorted(summary.items()):
        print(f"{sku}: {qty:.2f}")
    
    print("\n" + "=" * 80 + "\n")
    
    # Example 3: Explode FG002
    print(bom_tool.display_topology("FG002", 1.0))
    
    # Example 4: Show raw materials summary for FG002
    print("\nRAW MATERIALS SUMMARY FOR FG002:")
    print("-" * 40)
    summary = bom_tool.get_summary("FG002", 1.0)
    for sku, qty in sorted(summary.items()):
        print(f"{sku}: {qty:.2f}")


if __name__ == "__main__":
    main()
