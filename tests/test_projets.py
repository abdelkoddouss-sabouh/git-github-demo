from datetime import datetime
import unittest
from unittest.mock import patch
import fakeredis
import mongomock
import redis
from projet_a.executer import executer
from projet_b1.cache import Boutique, HITS, MISSES, mesurer
from projet_b1.generer import generer
from projet_b1.demo import benchmark


class ProjetsTests(unittest.TestCase):
    def setUp(self):
        self.r = fakeredis.FakeRedis(decode_responses=True)
        self.c = mongomock.MongoClient().boutique.commandes
        self.c.create_index("reference", unique=True)
        self.b = Boutique(self.c, self.r)

    def doc(self, ref="CMD-1", ville="Rabat", montant=50):
        return {"reference": ref, "client": {"nom": "A", "ville": ville},
                "categorie": "Livre", "montant": montant, "tags": []}

    def test_benchmark_rejects_missing_reference_without_clearing_cache(self):
        self.c.insert_one(self.doc())
        self.b.commande_avec_cache("CMD-1")
        with self.assertRaisesRegex(ValueError, "CMD-073412 absente"):
            benchmark(self.b, repetitions=1)
        self.assertEqual(self.r.get(MISSES), "1")
        self.assertEqual(self.b.commande_avec_cache("CMD-1")["montant"], 50)
        self.assertEqual(self.r.get(HITS), "1")

    def test_non_json_mongo_document_is_returned_without_caching(self):
        date = datetime(2026, 1, 1)
        self.c.insert_one(dict(self.doc(), date=date))

        with self.assertLogs(level="WARNING"):
            resultat = self.b.commande_avec_cache("CMD-1")

        self.assertEqual(resultat["date"], date)
        self.assertIsNone(self.r.get("b1:commande:CMD-1:details"))
        self.assertEqual(self.r.get(MISSES), "1")
        self.assertIsNone(self.r.get(HITS))

    def test_hit_miss_json_ttl(self):
        self.c.insert_one(self.doc())
        a = self.b.commande_avec_cache("CMD-1")
        self.assertNotIn("_id", a)
        self.assertEqual(a, self.b.commande_avec_cache("CMD-1"))
        self.assertEqual(self.r.get(HITS), "1")
        self.assertEqual(self.r.get(MISSES), "1")
        self.assertGreater(self.r.ttl("b1:commande:CMD-1:details"), 0)

    def test_invalidation_all_top_sizes_and_negative_cache(self):
        self.assertIsNone(self.b.commande_avec_cache("CMD-1"))
        self.b.ca_avec_cache()
        self.b.villes_avec_cache(1)
        self.b.villes_avec_cache(5)
        self.b.ajouter_commande(self.doc())
        self.assertEqual(self.b.ca_avec_cache()[0]["total"], 50)
        self.assertEqual(self.b.villes_avec_cache(1)[0]["_id"], "Rabat")
        self.assertEqual(self.b.villes_avec_cache(5)[0]["commandes"], 1)
        self.assertEqual(self.b.commande_avec_cache("CMD-1")["montant"], 50)

    def test_scan_failure_invalidates_known_keys_after_insert(self):
        self.assertIsNone(self.b.commande_avec_cache("CMD-1"))
        self.assertEqual(self.b.ca_avec_cache(), [])
        self.b.villes_avec_cache(5)
        with patch.object(self.r, "scan_iter", side_effect=redis.ConnectionError("scan failed")):
            with self.assertLogs(level="WARNING"):
                identifiant = self.b.ajouter_commande(self.doc())
        self.assertIsNotNone(identifiant)
        self.assertEqual(self.c.count_documents({}), 1)
        self.assertEqual(self.b.commande_avec_cache("CMD-1")["montant"], 50)
        self.assertEqual(self.b.ca_avec_cache(), [{"_id": "Livre", "total": 50}])
        # Les tops non parcourus restent bornés par leur TTL existant.
        self.assertGreater(self.r.ttl("b1:statistiques:top5:villes"), 0)

    def test_stale_then_invalidate(self):
        self.c.insert_one(self.doc())
        self.b.ca_avec_cache()
        self.c.insert_one(self.doc("CMD-2"))
        self.assertEqual(self.b.ca_avec_cache()[0]["total"], 50)
        self.b.invalider("CMD-2")
        self.assertEqual(self.b.ca_avec_cache()[0]["total"], 100)

    def test_redis_failure_reads_mongo(self):
        self.c.insert_one(self.doc())
        class Down:
            def get(self, key):
                raise redis.ConnectionError("offline")
        self.assertEqual(Boutique(self.c, Down()).commande_avec_cache("CMD-1")["montant"], 50)

    def test_corrupt_cache_and_scoped_clear(self):
        self.c.insert_one(self.doc())
        self.r.set("b1:commande:CMD-1:details", "{bad")
        self.assertEqual(self.b.commande_avec_cache("CMD-1")["montant"], 50)
        self.r.set("unrelated", "keep")
        self.b.vider_cache()
        self.assertEqual(self.r.get("unrelated"), "keep")
        self.assertEqual(list(self.r.scan_iter("b1:*")), [])

    def test_invalid_utf8_cache_is_replaced(self):
        self.c.insert_one(self.doc())
        key = "b1:commande:CMD-1:details"
        self.r.set(key, b"\xff")
        self.assertEqual(self.b.commande_avec_cache("CMD-1")["montant"], 50)
        self.assertEqual(self.r.get(MISSES), "1")
        self.assertEqual(self.b.commande_avec_cache("CMD-1")["montant"], 50)
        self.assertEqual(self.r.get(HITS), "1")

    def test_invalid_limits(self):
        for n in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                self.b.villes_avec_cache(n)
        with self.assertRaises(ValueError):
            mesurer(lambda: None, 0)

    def test_generator_rejects_invalid_counts_before_database_access(self):
        from unittest.mock import Mock
        collection = Mock()
        for nombre in (0, -1, True, 1.5, "12", None):
            with self.subTest(nombre=nombre):
                with self.assertRaisesRegex(ValueError, "entier positif"):
                    generer(collection, nombre)
        collection.count_documents.assert_not_called()
        collection.insert_many.assert_not_called()

    def test_generator_preserves_existing_data(self):
        self.assertEqual(generer(self.c, 12), 12)
        with self.assertRaises(ValueError):
            generer(self.c, 12)
        self.assertEqual(self.c.count_documents({}), 12)

    def test_quiz_unclosed_transaction_is_reported_and_discarded(self):
        with patch("projet_a.executer.COMMANDES") as fichier:
            fichier.read_text.return_value = "MULTI\nSET quiz:incomplete 1\n"
            with self.assertRaisesRegex(ValueError, "EXEC manquant"):
                executer(self.r, afficher=False)
        self.assertIsNone(self.r.get("quiz:incomplete"))
        self.assertTrue(self.r.ping())

    def test_quiz_rejects_invalid_transaction_boundaries(self):
        scripts = [
            ("# commentaire\nexec\n", "Ligne 2 : EXEC sans MULTI"),
            ("multi\nSET quiz:pending 1\nmulti\nexec\n", "Ligne 3 : MULTI imbriqué"),
        ]
        for script, erreur in scripts:
            with self.subTest(erreur=erreur):
                with patch("projet_a.executer.COMMANDES") as fichier:
                    fichier.read_text.return_value = script
                    with self.assertRaisesRegex(ValueError, erreur):
                        executer(self.r, afficher=False)
                self.assertIsNone(self.r.get("quiz:pending"))

    def test_quiz_exact_scores_badges_and_rerun(self):
        # Le reset doit aussi remplacer les anciens profils, même avec un type incompatible.
        self.r.set("joueur:j1:profil", "ancien-format")
        self.r.hset("joueur:j2:profil", "champ_obsolete", "reste")
        for _ in range(2):
            executer(self.r, afficher=False)
            self.assertEqual(self.r.zrevrange("classement:general:points", 0, -1, withscores=True),
                             [("j2", 73), ("j1", 55), ("j4", 46), ("j3", 43), ("j6", 15), ("j5", 8)])
            self.assertEqual(self.r.get("plateforme:quiz:parties"), "5")
            self.assertEqual(self.r.hget("joueur:j4:profil", "parties"), "2")
            self.assertIsNone(self.r.hget("joueur:j2:profil", "champ_obsolete"))
            self.assertEqual(self.r.llen("file:duels:attente"), 0)
            self.assertEqual(self.r.smembers("badge:invaincu:joueurs"), {"j2"})
            self.assertEqual(self.r.sdiff("plateforme:quiz:joueurs",
                                         "badge:premiere-victoire:joueurs",
                                         "badge:rapide:joueurs", "badge:invaincu:joueurs"), {"j6"})
            self.assertGreater(self.r.ttl("session:j1:active"), 0)


if __name__ == "__main__":
    unittest.main()

