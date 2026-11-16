"""Données synthétiques reproductibles : ne remplace pas le fichier du professeur."""
import argparse
import random
from projet_b1.cache import connecter


def generer(collection, nombre=100000):
    if not isinstance(nombre, int) or isinstance(nombre, bool) or nombre < 1:
        raise ValueError("nombre doit être un entier positif")
    if collection.count_documents({}):
        raise ValueError("Collection non vide : génération annulée pour préserver vos données.")
    rng = random.Random(42)
    villes = ["Rabat", "Casablanca", "Fes", "Tanger", "Marrakech", "Agadir"]
    categories = ["Livre", "Informatique", "Sport", "Maison"]
    lot = []
    for i in range(1, nombre + 1):
        lot.append({"reference": f"CMD-{i:06d}",
                    "client": {"nom": f"Client{rng.randrange(1, 10001):04d}",
                               "ville": rng.choice(villes)},
                    "categorie": rng.choice(categories),
                    "montant": rng.randrange(50, 5001),
                    "tags": [rng.choice(["promo", "nouveau", "standard"])]})
        if len(lot) == 1000 or i == nombre:
            collection.insert_many(lot)
            lot = []
    return collection.count_documents({})


def main():
    parser = argparse.ArgumentParser(description="Générer des commandes synthétiques.")
    parser.add_argument("--nombre", type=int, default=100000, help="Nombre de commandes")
    args = parser.parse_args()
    if args.nombre < 1:
        parser.error("--nombre doit être un entier positif")
    boutique = connecter()
    print("Commandes générées :", generer(boutique.commandes, args.nombre))


if __name__ == "__main__":
    main()
