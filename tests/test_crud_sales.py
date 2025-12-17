import tempfile
import unittest
from pathlib import Path

from inventory.config import AppConfig
from inventory.exceptions import ValidationError
from inventory.services import InventoryManager


class TestCRUD(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.db_path = self.tmp_path / "test.db"
        self.app = InventoryManager(AppConfig(db_path=str(self.db_path)))
        self.app.repo.create_schema_if_needed()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_add_product(self):
        product = self.app.add_product("P999", "Test", "Cat", 10.0, 5)
        self.assertEqual(product.sku, "P999")
        self.assertEqual(product.name, "Test")
        self.assertEqual(product.quantity, 5)

    def test_add_product_duplicate_sku(self):
        self.app.add_product("P999", "Test", "Cat", 10.0, 5)
        with self.assertRaises(ValidationError):
            self.app.add_product("P999", "Test2", "Cat", 20.0, 3)

    def test_update_product(self):
        self.app.add_product("P999", "Test", "Cat", 10.0, 5)
        updated = self.app.update_product("P999", name="Test2", quantity=10)
        self.assertEqual(updated.name, "Test2")
        self.assertEqual(updated.quantity, 10)

    def test_update_product_not_found(self):
        with self.assertRaises(ValidationError):
            self.app.update_product("P999", name="Test")

    def test_delete_product(self):
        self.app.add_product("P999", "Test", "Cat", 10.0, 5)
        self.app.delete_product("P999")
        product = self.app.repo.get_product_by_sku("P999")
        self.assertIsNone(product)

    def test_delete_product_not_found(self):
        with self.assertRaises(ValidationError):
            self.app.delete_product("P999")


class TestSales(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.db_path = self.tmp_path / "test.db"
        self.app = InventoryManager(AppConfig(db_path=str(self.db_path)))
        self.app.repo.create_schema_if_needed()
        self.app.add_product("P001", "Produit", "Cat", 10.0, 20)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_sell_product(self):
        result = self.app.sell_product("P001", 2)
        self.assertEqual(result["total_ht"], 20.0)
        self.assertEqual(result["total_vat"], 4.0)
        self.assertEqual(result["total_ttc"], 24.0)
        
        product = self.app.repo.get_product_by_sku("P001")
        self.assertEqual(product.quantity, 18)

    def test_sell_product_insufficient_stock(self):
        with self.assertRaises(ValidationError):
            self.app.sell_product("P001", 100)

    def test_sell_product_not_found(self):
        with self.assertRaises(ValidationError):
            self.app.sell_product("P999", 1)

    def test_dashboard(self):
        self.app.sell_product("P001", 2)
        self.app.sell_product("P001", 3)
        
        stats = self.app.get_dashboard()
        self.assertEqual(stats["nb_ventes"], 2)
        self.assertEqual(stats["qty_totale"], 5)
        self.assertEqual(stats["ca_ht"], 50.0)
        self.assertEqual(stats["tva_totale"], 10.0)
        self.assertEqual(stats["ca_ttc"], 60.0)

