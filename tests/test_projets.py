import unittest
from unittest.mock import patch
import fakeredis
import mongomock
import redis
from projet_a.executer import executer
from projet_b1.cache import Boutique, HITS, MISSES, mesurer
from projet_b1.generer import generer


class ProjetsTests(unittest.TestCase):
    def setUp(self):
        self.r = fakeredis.FakeRedis(decode_responses=True)
        self.c = mongomock.MongoClient().boutique.commandes
        self.c.create_index("reference", unique=True)
        self.b = Boutique(self.c, self.r)

    def doc(self, ref="CMD-1", ville="Rabat", montant=50):
        return {"reference": ref, "client": {"nom": "A", "ville": ville},
                "categorie": "Livre", "montant": montant, "tags": []}

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

    def test_invalid_limits(self):
        for n in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                self.b.villes_avec_cache(n)
        with self.assertRaises(ValueError):
            mesurer(lambda: None, 0)

    def test_generator_preserves_existing_data(self):
        self.assertEqual(generer(self.c, 12), 12)
        with self.assertRaises(ValueError):
            generer(self.c, 12)
        self.assertEqual(self.c.count_documents({}), 12)

    def test_quiz_exact_scores_badges_and_rerun(self):
        for _ in range(2):
            executer(self.r, afficher=False)
            self.assertEqual(self.r.zrevrange("classement:general:points", 0, -1, withscores=True),
                             [("j2", 73), ("j1", 55), ("j4", 46), ("j3", 43), ("j6", 15), ("j5", 8)])
            self.assertEqual(self.r.get("plateforme:quiz:parties"), "5")
            self.assertEqual(self.r.hget("joueur:j4:profil", "parties"), "2")
            self.assertEqual(self.r.llen("file:duels:attente"), 0)
            self.assertEqual(self.r.smembers("badge:invaincu:joueurs"), {"j2"})
            self.assertEqual(self.r.sdiff("plateforme:quiz:joueurs",
                                         "badge:premiere-victoire:joueurs",
                                         "badge:rapide:joueurs", "badge:invaincu:joueurs"), {"j6"})
            self.assertGreater(self.r.ttl("session:j1:active"), 0)


if __name__ == "__main__":
    unittest.main()

