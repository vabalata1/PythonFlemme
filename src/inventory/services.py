"""
services.py — Logique métier (use-cases)

Pourquoi ce fichier ?
- Centraliser la logique métier (et pas dans la CLI).
- Orchestrer validation + repository + calculs.
- Avoir des fonctions facilement testables.

Ce qui est déjà fait :
- Initialisation JSON → SQLite (reset DB)
- Listing inventaire

Ce que vous devez faire :
- Implémenter les autres use-cases : CRUD, vente, dashboard, export.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from .config import AppConfig
from .exceptions import ValidationError
from .models import Product, now_iso
from .repository import SQLiteRepository
from .utils import load_initial_json

logger = logging.getLogger(__name__)


class InventoryManager:
    """Service principal du domaine 'stock'."""

    def __init__(self, config: AppConfig, repo: Optional[SQLiteRepository] = None) -> None:
        self.config = config
        self.repo = repo or SQLiteRepository(config.db_path)

    def initialize_from_json(self, json_path: str, reset: bool = True) -> int:
        """Initialise la DB depuis un JSON."""
        logger.info("Initialization requested from JSON: %s", json_path)
        payload = load_initial_json(json_path)
        products = payload["products"]

        if reset:
            self.repo.reset_and_create_schema()
        else:
            self.repo.create_schema_if_needed()

        count = 0
        for p in products:
            prod = Product(
                sku=p["sku"],
                name=p["name"],
                category=p["category"],
                unit_price_ht=p["unit_price_ht"],
                quantity=p["quantity"],
                vat_rate=p["vat_rate"],
                created_at=now_iso(),
            )
            self.repo.insert_product(prod)
            count += 1

        logger.info("Initialization OK. %d products inserted.", count)
        return count

    def list_inventory(self) -> List[Product]:
        """Retourne la liste des produits (inventaire)."""
        self.repo.create_schema_if_needed()
        return self.repo.list_products()

    def add_product(self, sku: str, name: str, category: str, unit_price_ht: float, quantity: int, vat_rate: Optional[float] = None) -> Product:
        if unit_price_ht < 0:
            raise ValidationError("prix negatif pas possible")
        if quantity < 0:
            raise ValidationError("quantite negatif pas possible")
        if vat_rate is not None and (vat_rate < 0 or vat_rate > 1):
            raise ValidationError("tva doit etre entre 0 et 1")
        
        existing = self.repo.get_product_by_sku(sku)
        if existing:
            raise ValidationError(f"SKU {sku} existe deja")
        
        vat = vat_rate if vat_rate is not None else self.config.default_vat_rate
        product = Product(
            sku=sku,
            name=name,
            category=category,
            unit_price_ht=round(unit_price_ht, 2),
            vat_rate=vat,
            quantity=quantity,
            created_at=now_iso()
        )
        self.repo.insert_product(product)
        logger.info("produit ajoute: %s", sku)
        return product

    def update_product(self, sku: str, **updates) -> Product:
        product = self.repo.get_product_by_sku(sku)
        if not product:
            raise ValidationError(f"produit {sku} pas trouve")
        
        if "unit_price_ht" in updates and updates["unit_price_ht"] < 0:
            raise ValidationError("prix negatif pas possible")
        if "quantity" in updates and updates["quantity"] < 0:
            raise ValidationError("quantite negatif pas possible")
        if "vat_rate" in updates and (updates["vat_rate"] < 0 or updates["vat_rate"] > 1):
            raise ValidationError("tva doit etre entre 0 et 1")
        
        if "unit_price_ht" in updates:
            updates["unit_price_ht"] = round(updates["unit_price_ht"], 2)
        
        self.repo.update_product(sku, **updates)
        logger.info("produit modifie: %s", sku)
        updated = self.repo.get_product_by_sku(sku)
        return updated

    def delete_product(self, sku: str) -> None:
        product = self.repo.get_product_by_sku(sku)
        if not product:
            raise ValidationError(f"produit {sku} pas trouve")
        
        try:
            self.repo.delete_product(sku)
            logger.info("produit supprime: %s", sku)
        except DatabaseError as e:
            if "lie" in str(e) or "ventes" in str(e):
                raise ValidationError(f"impossible de supprimer {sku}: produit a des ventes")
            raise

    def sell_product(self, sku: str, quantity: int) -> dict:
        if quantity <= 0:
            raise ValidationError("quantite doit etre > 0")
        
        product = self.repo.get_product_by_sku(sku)
        if not product:
            raise ValidationError(f"produit {sku} pas trouve")
        
        if product.quantity < quantity:
            raise ValidationError(f"stock pas assez. il reste: {product.quantity}")
        
        total_ht = round(product.unit_price_ht * quantity, 2)
        total_vat = round(total_ht * product.vat_rate, 2)
        total_ttc = round(total_ht + total_vat, 2)
        
        from .models import Sale
        sale = Sale(
            product_id=product.id,
            sku=sku,
            quantity=quantity,
            unit_price_ht=product.unit_price_ht,
            vat_rate=product.vat_rate,
            total_ht=total_ht,
            total_vat=total_vat,
            total_ttc=total_ttc,
            sold_at=now_iso()
        )
        
        self.repo.sell_product(sale)
        logger.info("vente ok: %s x%d", sku, quantity)
        
        return {
            "total_ht": total_ht,
            "total_vat": total_vat,
            "total_ttc": total_ttc
        }

    def get_dashboard(self) -> dict:
        return self.repo.get_dashboard_stats()
