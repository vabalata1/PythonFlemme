"""
cli.py — Interface console (menu interactif)

Pourquoi ce fichier ?
- C’est la couche “présentation” : inputs utilisateur, affichage, navigation menu.
- Elle doit rester simple : pas de SQL direct ici, pas de calcul métier complexe ici.

Ce qui est déjà fait (starter) :
- Menu interactif complet (8 options)
- Option 1 : Initialisation JSON → SQLite (fonctionnelle)
- Option 2 : Afficher inventaire (fonctionnelle)
- Les options 3 à 7 sont des TODO guidés

Ce que vous devez faire :
- Implémenter progressivement les options 3..7 en appelant `InventoryManager`.
"""

from __future__ import annotations

import argparse
import logging

from .config import AppConfig
from .exceptions import (
    DataImportError,
    DatabaseError,
    InventoryError,
    ValidationError,
)
from .logging_conf import configure_logging
from .services import InventoryManager
from .utils import format_table

logger = logging.getLogger(__name__)


def _prompt(text: str) -> str:
    return input(text).strip()


def print_menu() -> None:
    print("\n=== Gestion de stock (JSON -> SQLite) ===")
    print("1) Initialiser le stock (depuis un JSON)")
    print("2) Afficher l’inventaire")
    print("3) Ajouter un produit")
    print("4) Modifier un produit")
    print("5) Supprimer un produit")
    print("6) Vendre un produit")
    print("7) Tableau de bord")
    print("8) Quitter")


def render_inventory_table(products) -> str:
    headers = ["ID", "SKU", "Nom", "Catégorie", "Prix HT", "TVA", "Prix TTC", "Stock"]
    rows = []
    for p in products:
        unit_ttc = round(p.unit_price_ht * (1 + p.vat_rate), 2)
        rows.append([
            str(p.id or ""),
            p.sku,
            p.name,
            p.category,
            f"{p.unit_price_ht:.2f}",
            f"{p.vat_rate:.2f}",
            f"{unit_ttc:.2f}",
            str(p.quantity),
        ])
    return format_table(headers, rows)


def action_initialize(app: InventoryManager) -> None:
    default_path = "data/initial_stock.json"
    path = _prompt(f"Chemin du JSON d'initialisation [{default_path}] : ")
    path = path or default_path
    count = app.initialize_from_json(path, reset=True)
    print(f"Initialisation réussie : {count} produit(s) importé(s).")


def action_list_inventory(app: InventoryManager) -> None:
    products = app.list_inventory()
    if not products:
        print("(inventaire vide)")
        return
    print("\n" + render_inventory_table(products))


def action_add_product(app: InventoryManager) -> None:
    sku = _prompt("SKU: ")
    if not sku:
        print("faut un SKU")
        return
    
    name = _prompt("Nom: ")
    if not name:
        print("faut un nom")
        return
    
    category = _prompt("Categorie: ")
    if not category:
        print("faut une categorie")
        return
    
    try:
        price = float(_prompt("Prix HT: "))
    except ValueError:
        print("prix pas bon")
        return
    
    try:
        qty = int(_prompt("Quantite: "))
    except ValueError:
        print("quantite pas bonne")
        return
    
    vat_input = _prompt("TVA (defaut 20%) [Entree pour defaut]: ").strip()
    vat = None
    if vat_input:
        try:
            vat = float(vat_input)
        except ValueError:
            print("TVA pas bonne")
            return
    
    try:
        product = app.add_product(sku, name, category, price, qty, vat)
        print(f"produit {product.sku} ajoute")
    except ValidationError as e:
        print(f"erreur: {e}")


def action_update_product(app: InventoryManager) -> None:
    sku = _prompt("SKU du produit a modifier: ")
    if not sku:
        print("faut un SKU")
        return
    
    updates = {}
    
    name = _prompt("Nouveau nom [Entree pour ignorer]: ").strip()
    if name:
        updates["name"] = name
    
    category = _prompt("Nouvelle categorie [Entree pour ignorer]: ").strip()
    if category:
        updates["category"] = category
    
    price_input = _prompt("Nouveau prix HT [Entree pour ignorer]: ").strip()
    if price_input:
        try:
            updates["unit_price_ht"] = float(price_input)
        except ValueError:
            print("prix pas bon")
            return
    
    qty_input = _prompt("Nouvelle quantite [Entree pour ignorer]: ").strip()
    if qty_input:
        try:
            updates["quantity"] = int(qty_input)
        except ValueError:
            print("quantite pas bonne")
            return
    
    vat_input = _prompt("Nouveau taux TVA [Entree pour ignorer]: ").strip()
    if vat_input:
        try:
            updates["vat_rate"] = float(vat_input)
        except ValueError:
            print("TVA pas bonne")
            return
    
    if not updates:
        print("rien a modifier")
        return
    
    try:
        product = app.update_product(sku, **updates)
        print(f"produit {product.sku} modifie")
    except ValidationError as e:
        print(f"erreur: {e}")


def action_delete_product(app: InventoryManager) -> None:
    sku = _prompt("SKU du produit a supprimer: ")
    if not sku:
        print("faut un SKU")
        return
    
    confirm = _prompt(f"Confirmer suppression de {sku} ? (o/N): ")
    if confirm.lower() != "o":
        print("annule")
        return
    
    try:
        app.delete_product(sku)
        print(f"produit {sku} supprime")
    except ValidationError as e:
        print(f"erreur: {e}")


def action_sell_product(app: InventoryManager) -> None:
    sku = _prompt("SKU du produit a vendre: ")
    if not sku:
        print("faut un SKU")
        return
    
    try:
        qty = int(_prompt("Quantite: "))
    except ValueError:
        print("quantite pas bonne")
        return
    
    try:
        result = app.sell_product(sku, qty)
        print(f"\nVente ok:")
        print(f"  Total HT: {result['total_ht']:.2f} €")
        print(f"  TVA: {result['total_vat']:.2f} €")
        print(f"  Total TTC: {result['total_ttc']:.2f} €")
    except ValidationError as e:
        print(f"erreur: {e}")


def action_dashboard(app: InventoryManager) -> None:
    stats = app.get_dashboard()
    print("\n=== Tableau de bord ===")
    print(f"Nombre de ventes: {stats['nb_ventes']}")
    print(f"Quantite vendue totale: {stats['qty_totale']}")
    print(f"CA HT: {stats['ca_ht']:.2f} €")
    print(f"TVA totale: {stats['tva_totale']:.2f} €")
    print(f"CA TTC: {stats['ca_ttc']:.2f} €")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Inventory CLI — starter kit")
    p.add_argument("--db", default="data/inventory.db", help="Chemin du fichier SQLite (.db)")
    p.add_argument("--log-level", default="INFO", help="DEBUG/INFO/WARNING/ERROR")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    configure_logging(log_level=args.log_level)
    config = AppConfig(db_path=args.db)
    app = InventoryManager(config)

    logger.info("App started with db=%s", config.db_path)

    while True:
        try:
            print_menu()
            choice = _prompt("Votre choix (1-8) : ")

            if choice == "1":
                action_initialize(app)
            elif choice == "2":
                action_list_inventory(app)
            elif choice == "3":
                action_add_product(app)
            elif choice == "4":
                action_update_product(app)
            elif choice == "5":
                action_delete_product(app)
            elif choice == "6":
                action_sell_product(app)
            elif choice == "7":
                action_dashboard(app)
            elif choice == "8":
                print("au revoir.")
                return 0
            else:
                print("choix pas bon. entre 1 et 8.")

        except (ValidationError, DataImportError) as e:
            logger.warning("Validation/import error: %s", e)
            print(f"erreur: {e}")
        except DatabaseError as e:
            logger.error("Database error: %s", e)
            print(f"erreur base de donnees: {e}")
        except InventoryError as e:
            logger.error("Inventory error: %s", e)
            print(f"erreur: {e}")
        except KeyboardInterrupt:
            print("\ninterruption. au revoir.")
            return 130
        except Exception:
            logger.exception("Unexpected error")
            print("erreur inattendue. regarde les logs.")
            return 1
