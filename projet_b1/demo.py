"""Exécuter avec python -m projet_b1.demo ; mesures locales réelles uniquement."""
import argparse
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from projet_b1.cache import connecter, mesurer, HITS, MISSES


def benchmark(boutique, repetitions=100, *, reference="CMD-073412"):
    if boutique.commande_par_reference(reference) is None:
        raise ValueError(f"Référence {reference} absente : choisir une commande existante.")
    lignes = []
    fonctions = [
        ("Reference", lambda: boutique.commande_par_reference(reference),
         lambda: boutique.commande_avec_cache(reference)),
        ("CA categories", boutique.chiffre_affaires_par_categorie, boutique.ca_avec_cache),
        ("Top villes", boutique.top_villes, boutique.villes_avec_cache),
    ]
    for nom, direct, cache in fonctions:
        sans = mesurer(direct, repetitions)
        boutique.vider_cache()
        premier = mesurer(cache, 1)
        suivants = mesurer(cache, repetitions)
        hits = int(boutique.cache.get(HITS) or 0)
        misses = int(boutique.cache.get(MISSES) or 0)
        lignes.append({"fonction": nom, "sans_cache_ms": sans, "premier_ms": premier,
                       "suivants_ms": suivants, "gain": sans / suivants if suivants else 0,
                       "hits": hits, "misses": misses,
                       "taux_succes": hits / (hits + misses) if hits + misses else 0})
    return lignes


def total_livre(boutique):
    return next((x["total"] for x in boutique.ca_avec_cache() if x["_id"] == "Livre"), 0)


def demonstration_invalidation(boutique):
    ref = "CMD-100001"
    if boutique.commandes.find_one({"reference": ref}):
        raise ValueError("CMD-100001 existe déjà : démonstration annulée, aucune suppression.")
    document = {"reference": ref, "client": {"nom": "Client0001", "ville": "Rabat"},
                "categorie": "Livre", "montant": 5000, "tags": ["promo"]}
    boutique.vider_cache()
    avant = total_livre(boutique)
    identifiant = None
    try:
        identifiant = boutique.commandes.insert_one(dict(document)).inserted_id
        print("Avant :", avant, "| Après insertion directe (cache) :", total_livre(boutique))
        boutique.commandes.delete_one({"_id": identifiant})
        identifiant = None
        identifiant = boutique.ajouter_commande(document)
        apres = total_livre(boutique)
        print("Après insertion avec invalidation :", apres)
        assert apres == avant + 5000
    finally:
        if identifiant is not None:
            boutique.commandes.delete_one({"_id": identifiant})
        boutique.invalider(ref)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=100)
    parser.add_argument("--reference", default="CMD-073412", help="Référence à mesurer")
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions doit être positif")
    boutique = connecter()
    nombre = boutique.commandes.count_documents({})
    if not nombre:
        raise SystemExit("Base vide : lancer python -m projet_b1.generer")
    print("Nombre de commandes :", nombre)
    try:
        lignes = benchmark(boutique, args.repetitions, reference=args.reference)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    dossier = Path("resultats")
    dossier.mkdir(exist_ok=True)
    with (dossier / "mesures.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(lignes[0]))
        writer.writeheader()
        writer.writerows(lignes)
    for ligne in lignes:
        print(ligne)
    x = list(range(len(lignes)))
    fig, ax = plt.subplots()
    ax.bar([i - .2 for i in x], [l["sans_cache_ms"] for l in lignes], .4, label="Sans cache")
    ax.bar([i + .2 for i in x], [l["suivants_ms"] for l in lignes], .4, label="Avec cache")
    ax.set_xticks(x, [l["fonction"] for l in lignes])
    ax.set_ylabel("Temps moyen (ms)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(dossier / "comparaison.png")
    plt.close(fig)
    demonstration_invalidation(boutique)


if __name__ == "__main__":
    main()
