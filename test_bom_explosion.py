"""
Tests for BOM Explosion Tool
"""

import unittest
from bom_explosion import BOMExplosion, create_sample_bom_data


class TestBOMExplosion(unittest.TestCase):
    """Test cases for BOM explosion functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.bom_data = create_sample_bom_data()
        self.bom_tool = BOMExplosion(self.bom_data)
    
    def test_simple_raw_material(self):
        """Test explosion of a raw material (no components)"""
        result = self.bom_tool.explode("RM001", 1.0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], "RM001")
        self.assertEqual(result[0][3], "Raw Material")
    
    def test_finished_good_explosion(self):
        """Test explosion of a finished good"""
        result = self.bom_tool.explode("FG001", 1.0)
        # Should have FG001 plus its direct components and their sub-components
        self.assertGreater(len(result), 1)
        self.assertEqual(result[0][1], "FG001")
        self.assertEqual(result[0][3], "Finished Good")
    
    def test_quantity_multiplication(self):
        """Test that quantities are correctly multiplied through levels"""
        result = self.bom_tool.explode("FG001", 2.0)
        # FG001 should be quantity 2.0
        self.assertEqual(result[0][2], 2.0)
        # Check that component quantities are also doubled
        for level, sku, qty, item_type in result:
            if level == 1 and sku == "COMP001":
                # COMP001 requires 2.0 per FG001, so 4.0 for 2 FG001
                self.assertEqual(qty, 4.0)
    
    def test_summary_aggregation(self):
        """Test that raw materials are correctly aggregated in summary"""
        summary = self.bom_tool.get_summary("FG001", 1.0)
        # RM001 (Screws) appears in multiple places:
        # - 4.0 directly in FG001
        # - 8.0 in COMP001 (x2 = 16.0)
        # - 4.0 in COMP002
        # Total should be 4 + 16 + 4 = 24
        self.assertEqual(summary["RM001"], 24.0)
    
    def test_compound_identification(self):
        """Test that compounds are correctly identified"""
        result = self.bom_tool.explode("FG001", 1.0)
        compounds = [item for item in result if item[3] == "Compound"]
        self.assertGreater(len(compounds), 0)
        # COMP001 and COMP002 should be identified as compounds
        compound_skus = [item[1] for item in compounds]
        self.assertIn("COMP001", compound_skus)
        self.assertIn("COMP002", compound_skus)
    
    def test_display_topology_format(self):
        """Test that topology display returns a formatted string"""
        topology = self.bom_tool.display_topology("FG001", 1.0)
        self.assertIsInstance(topology, str)
        self.assertIn("FG001", topology)
        self.assertIn("BOM EXPLOSION FOR", topology)
        self.assertIn("Finished Good", topology)
    
    def test_circular_reference_detection(self):
        """Test circular reference detection"""
        # Create BOM data with circular reference
        circular_bom = {
            "A": [("B", 1.0)],
            "B": [("C", 1.0)],
            "C": [("A", 1.0)],  # Circular reference back to A
        }
        circular_tool = BOMExplosion(circular_bom)
        result = circular_tool.explode("A", 1.0)
        # Should detect circular reference
        error_items = [item for item in result if "CIRCULAR REFERENCE" in item[1]]
        self.assertGreater(len(error_items), 0)
    
    def test_multiple_finished_goods(self):
        """Test explosion of different finished goods"""
        result_fg001 = self.bom_tool.explode("FG001", 1.0)
        result_fg002 = self.bom_tool.explode("FG002", 1.0)
        # Both should have results
        self.assertGreater(len(result_fg001), 0)
        self.assertGreater(len(result_fg002), 0)
        # They should have different raw materials
        summary_fg001 = self.bom_tool.get_summary("FG001", 1.0)
        summary_fg002 = self.bom_tool.get_summary("FG002", 1.0)
        self.assertNotEqual(summary_fg001, summary_fg002)


if __name__ == "__main__":
    unittest.main()
