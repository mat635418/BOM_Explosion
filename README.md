# BOM Explosion Tool

A Python tool to analyze and display BOM (Bill of Materials) explosions for finished goods, showing the complete topology of all compounds and raw materials involved.

## Features

- **BOM Explosion**: Recursively expands a finished good SKU into all its component parts
- **Topology Display**: Shows hierarchical structure in a tree-like format
- **Raw Materials Summary**: Aggregates all raw materials needed with total quantities
- **Circular Reference Detection**: Detects and reports circular dependencies in BOM structure
- **Quantity Calculation**: Correctly multiplies quantities through all BOM levels

## Installation

No external dependencies required - uses only Python standard library.

```bash
git clone https://github.com/mat635418/BOM_Explosion.git
cd BOM_Explosion
```

## Usage

### Running the Demo

```bash
python3 bom_explosion.py
```

This will display BOM explosions for sample finished goods with their complete material breakdowns.

### Running the Examples

```bash
python3 examples.py
```

This will run multiple examples showing different use cases:
- Custom BOM data (bike assembly example)
- Different quantity calculations
- Comparing multiple products
- Interactive exploration

### Using in Your Code

```python
from bom_explosion import BOMExplosion

# Define your BOM data structure
bom_data = {
    "FG001": [("COMP001", 2.0), ("RM001", 4.0)],
    "COMP001": [("RM002", 3.0), ("RM003", 1.0)],
    "RM001": [],  # Raw materials have no components
    "RM002": [],
    "RM003": [],
}

# Initialize the tool
bom_tool = BOMExplosion(bom_data)

# Display topology for a finished good
print(bom_tool.display_topology("FG001", quantity=1.0))

# Get raw materials summary
summary = bom_tool.get_summary("FG001", quantity=1.0)
print(summary)
```

## BOM Data Structure

The BOM data is a dictionary where:
- **Key**: SKU (Stock Keeping Unit) identifier
- **Value**: List of tuples, each containing:
  - Component SKU
  - Quantity required per parent unit

Example:
```python
{
    "FG001": [("COMP001", 2.0), ("RM001", 4.0)],  # Finished Good
    "COMP001": [("RM002", 3.0)],                   # Compound
    "RM001": [],                                    # Raw Material
    "RM002": [],                                    # Raw Material
}
```

## Testing

Run the test suite:

```bash
python3 -m unittest test_bom_explosion -v
```

## Example Output

```
================================================================================
BOM EXPLOSION FOR: FG001 (Quantity: 1.0)
================================================================================

FG001 (Qty: 1.00) [Finished Good]
  └─ COMP001 (Qty: 2.00) [Compound]
    └─ RM003 (Qty: 4.00) [Raw Material]
    └─ RM004 (Qty: 2.00) [Raw Material]
    └─ RM001 (Qty: 16.00) [Raw Material]
  └─ COMP002 (Qty: 1.00) [Compound]
    └─ RM005 (Qty: 1.00) [Raw Material]
    └─ RM006 (Qty: 1.00) [Raw Material]
    └─ RM001 (Qty: 4.00) [Raw Material]
  └─ RM001 (Qty: 4.00) [Raw Material]

================================================================================
```

## Item Types

- **Finished Good**: Top-level product (input SKU)
- **Compound**: Intermediate assembly with sub-components
- **Raw Material**: Leaf-level material with no further breakdown

## License

MIT License
