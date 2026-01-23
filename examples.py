#!/usr/bin/env python3
"""
Example usage script for BOM Explosion Tool

This script demonstrates how to use the BOM explosion tool with custom data.
You can modify the bom_data dictionary to match your own product structure.
"""

from bom_explosion import BOMExplosion, create_sample_bom_data


def example_with_custom_data():
    """Example with simple custom BOM data"""
    print("=" * 80)
    print("EXAMPLE 1: Simple Custom BOM")
    print("=" * 80)
    
    # Define a simple BOM structure
    custom_bom = {
        "BIKE-001": [
            ("FRAME-001", 1.0),
            ("WHEEL-001", 2.0),
            ("SEAT-001", 1.0),
        ],
        "FRAME-001": [
            ("STEEL-TUBE", 3.0),
            ("WELD-JOINT", 6.0),
            ("PAINT-BLACK", 0.5),
        ],
        "WHEEL-001": [
            ("RIM-001", 1.0),
            ("TIRE-001", 1.0),
            ("SPOKE-001", 36.0),
        ],
        "SEAT-001": [
            ("FOAM-PAD", 1.0),
            ("LEATHER-COVER", 1.0),
            ("SEAT-POST", 1.0),
        ],
        # Raw materials
        "STEEL-TUBE": [],
        "WELD-JOINT": [],
        "PAINT-BLACK": [],
        "RIM-001": [],
        "TIRE-001": [],
        "SPOKE-001": [],
        "FOAM-PAD": [],
        "LEATHER-COVER": [],
        "SEAT-POST": [],
    }
    
    bike_tool = BOMExplosion(custom_bom)
    print(bike_tool.display_topology("BIKE-001", 1.0))
    
    print("\nRAW MATERIALS NEEDED FOR 1 BIKE:")
    print("-" * 40)
    summary = bike_tool.get_summary("BIKE-001", 1.0)
    for sku, qty in sorted(summary.items()):
        print(f"{sku}: {qty:.2f}")
    print()


def example_with_different_quantities():
    """Example showing quantity calculations"""
    print("=" * 80)
    print("EXAMPLE 2: Different Quantities")
    print("=" * 80)
    
    bom_data = create_sample_bom_data()
    bom_tool = BOMExplosion(bom_data)
    
    for quantity in [1.0, 5.0, 10.0]:
        print(f"\nRAW MATERIALS FOR {quantity:.0f} units of FG001:")
        print("-" * 40)
        summary = bom_tool.get_summary("FG001", quantity)
        for sku, qty in sorted(summary.items()):
            print(f"{sku}: {qty:.2f}")


def example_comparing_products():
    """Example comparing different products"""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Comparing Products")
    print("=" * 80)
    
    bom_data = create_sample_bom_data()
    bom_tool = BOMExplosion(bom_data)
    
    products = ["FG001", "FG002"]
    
    for product in products:
        print(f"\n{product} Summary:")
        print("-" * 40)
        summary = bom_tool.get_summary(product, 1.0)
        for sku, qty in sorted(summary.items()):
            print(f"  {sku}: {qty:.2f}")


def interactive_mode():
    """Interactive mode for exploring BOM data"""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Interactive Mode")
    print("=" * 80)
    
    bom_data = create_sample_bom_data()
    bom_tool = BOMExplosion(bom_data)
    
    print("\nAvailable SKUs in sample data:")
    for sku in sorted(bom_data.keys()):
        components = bom_data[sku]
        if not components:
            item_type = "Raw Material"
        elif sku.startswith("FG"):
            item_type = "Finished Good"
        else:
            item_type = "Compound"
        print(f"  {sku} - {item_type}")
    
    print("\nYou can explore any SKU by modifying this script or using the BOMExplosion class directly.")


if __name__ == "__main__":
    print("BOM EXPLOSION TOOL - USAGE EXAMPLES")
    print("=" * 80)
    print()
    
    # Run all examples
    example_with_custom_data()
    example_with_different_quantities()
    example_comparing_products()
    interactive_mode()
    
    print("\n" + "=" * 80)
    print("All examples completed successfully!")
    print("=" * 80)
