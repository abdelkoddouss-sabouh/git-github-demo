"""Cache-aside pédagogique, destiné à une démonstration sans écritures concurrentes."""
import json
import logging
import os
from time import perf_counter

import redis
from pymongo import MongoClient

PREFIX = "b1:"
HITS = PREFIX + "statistiques:cache:hits"
MISSES = PREFIX + "statistiques:cache:misses"


def mesurer(fonction, repetitions=100):
    if repetitions < 1:
        raise ValueError("repetitions doit être positif")
    debut = perf_counter()
    for _ in range(repetitions):
        fonction()
    return (perf_counter() - debut) * 1000 / repetitions


class Boutique:
    def __init__(self, collection, cache):
        self.commandes = collection
        self.cache = cache

    def commande_par_reference(self, reference):
        return self.commandes.find_one({"reference": reference}, {"_id": 0})

    def chiffre_affaires_par_categorie(self):
        return list(self.commandes.aggregate([
            {"$group": {"_id": "$categorie", "total": {"$sum": "$montant"}}},
            {"$sort": {"total": -1, "_id": 1}},
        ]))

    def top_villes(self, n=5):
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            raise ValueError("n doit être un entier positif")
        return list(self.commandes.aggregate([
            {"$group": {"_id": "$client.ville", "commandes": {"$sum": 1}}},
            {"$sort": {"commandes": -1, "_id": 1}},
            {"$limit": n},
        ]))

    def _compter(self, cle):
        try:
            self.cache.incr(cle)
        except redis.RedisError:
            logging.warning("Compteurs Redis indisponibles")

    def _avec_cache(self, cle, charger, types_attendus):
        try:
            valeur = self.cache.get(cle)
        except UnicodeDecodeError:
            valeur = None  # Redis a renvoyé une valeur qui ne se décode pas en UTF-8.
        except redis.RedisError:
            logging.warning("Redis indisponible : lecture directe dans MongoDB")
            return charger()
        if valeur is not None:
            try:
                resultat = json.loads(valeur)
            except (ValueError, TypeError):
                pass  # Valeur corrompue : la remplacer depuis MongoDB.
            else:
                if isinstance(resultat, types_attendus):
                    self._compter(HITS)
                    return resultat
        self._compter(MISSES)
        resultat = charger()
        try:
            contenu = json.dumps(resultat, ensure_ascii=False)
        except TypeError:
            logging.warning("Résultat MongoDB non sérialisable en JSON, cache ignoré")
            return resultat
        try:
            self.cache.set(cle, contenu, ex=60)
        except redis.RedisError:
            logging.warning("Résultat lu, mais non enregistré dans Redis")
        return resultat

    def commande_avec_cache(self, reference):
        return self._avec_cache(PREFIX + f"commande:{reference}:details",
                                lambda: self.commande_par_reference(reference),
                                (dict, type(None)))

    def ca_avec_cache(self):
        return self._avec_cache(PREFIX + "statistiques:categories:ca",
                                self.chiffre_affaires_par_categorie, list)

    def villes_avec_cache(self, n=5):
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            raise ValueError("n doit être un entier positif")
        return self._avec_cache(PREFIX + f"statistiques:top{n}:villes",
                                lambda: self.top_villes(n), list)

    def vider_cache(self):
        # Pas de FLUSHDB : seules les clés de CE projet sont concernées.
        cles = list(self.cache.scan_iter(match=PREFIX + "*"))
        if cles:
            self.cache.delete(*cles)

    def invalider(self, reference):
        cles = [PREFIX + f"commande:{reference}:details",
                PREFIX + "statistiques:categories:ca"]
        # Invalider les clés connues même si le parcours des tops échoue ensuite.
        self.cache.delete(*cles)
        tops = list(self.cache.scan_iter(match=PREFIX + "statistiques:top*:villes"))
        if tops:
            self.cache.delete(*tops)

    def ajouter_commande(self, document):
        for champ in ("reference", "client", "categorie", "montant"):
            if champ not in document:
                raise ValueError(f"Champ manquant : {champ}")
        if not isinstance(document["client"], dict) or "ville" not in document["client"]:
            raise ValueError("client.ville est obligatoire")
        resultat = self.commandes.insert_one(dict(document))
        try:
            self.invalider(document["reference"])
        except redis.RedisError:
            # Ne pas réessayer l'insertion : elle a déjà réussi dans MongoDB.
            logging.warning("Commande insérée ; invalidation impossible. "
                            "Le cache restant peut être périmé jusqu'à son TTL de 60 s.")
        return resultat.inserted_id


def connecter():
    mongo = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27018"),
                        serverSelectionTimeoutMS=3000)
    mongo.admin.command("ping")
    cache = redis.Redis.from_url(os.getenv("REDIS_CACHE_URL", "redis://localhost:6380/0"),
                                 decode_responses=True, socket_timeout=3,
                                 socket_connect_timeout=3)
    cache.ping()
    collection = mongo[os.getenv("MONGO_DB", "boutique")].commandes
    collection.create_index("reference", unique=True)
    return Boutique(collection, cache)

