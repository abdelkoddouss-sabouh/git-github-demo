# B1 — Cache Redis devant MongoDB

Depuis la racine du dépôt, une fois les services démarrés :
```powershell
python -m projet_b1.generer
python -m projet_b1.demo
```

Le générateur crée 100 000 commandes synthétiques reproductibles uniquement si la collection est vide.
Ce n'est pas le fichier commandes_donnees.js du professeur. Schéma utilisé :
```json
{"reference":"CMD-073412","client":{"nom":"Client0001","ville":"Rabat"},"categorie":"Livre","montant":5000,"tags":["promo"]}
```
Si `CMD-073412` est absente, lancer `python -m projet_b1.demo --reference CMD-000001`
en remplaçant `CMD-000001` par une référence présente dans la collection.
Pour d'autres données, vérifier notamment le chemin client.ville et les montants numériques.
La référence est indexée et unique. La recherche par référence exclut `_id`.
Un résultat non sérialisable en JSON, par exemple une commande avec une date BSON,
est renvoyé depuis MongoDB sans être mis en cache.

## Fonctionnement

- Requêtes : commande par référence, CA par catégorie, top N villes.
- Cache-aside JSON, TTL 60 s ; un résultat absent (null) est aussi mis en cache.
- Clés : b1:commande:REFERENCE:details, b1:statistiques:categories:ca,
  b1:statistiques:topN:villes ; compteurs b1:statistiques:cache:hits et misses.
- Les clés de chaque top N, le CA et la référence concernée sont invalidés après insertion.
  Le CA et la référence sont supprimés avant le parcours des tops : si ce parcours échoue,
  seuls les tops non invalidés peuvent rester périmés jusqu'à leur TTL.
- Les trois mesures distinguent MongoDB seul, premier appel froid et moyenne des suivants.
  Le CSV indique aussi hits/misses et taux de succès propres à chaque série.
  Le benchmark s’arrête avant l’export si une série ne contient aucun hit Redis
  ou si les compteurs ne correspondent pas au nombre de lectures.
- Résultats réels dans resultats/mesures.csv et comparaison.png. Aucun gain n'est prérempli.
- Démonstration CMD-100001 : insertion directe périmant le cache, puis insertion avec
  invalidation. La commande temporaire est retirée à la fin. Si elle existe déjà, la démo refuse de la supprimer.
- Redis doit fonctionner au démarrage et pendant le benchmark ; les lectures de Boutique
  basculent sur MongoDB en cas de panne Redis ultérieure.

Variables facultatives : MONGO_URI (défaut mongodb://localhost:27018),
MONGO_DB (boutique), REDIS_CACHE_URL (redis://localhost:6380/0).

## Limites de cette démonstration

Exécuter sans écritures concurrentes : MongoDB et Redis ne partagent pas de transaction.
Une écriture concurrente peut laisser un cache périmé jusqu'au TTL ; une invalidation échouée
est signalée après l'insertion réussie. Ne pas réinsérer aveuglément la même commande.
Les suppressions faites directement dans MongoDB nécessitent aussi une invalidation.
Un benchmark dépassant 60 secondes peut inclure des expirations ; contrôler les compteurs.
Un index peut rendre la recherche par référence déjà rapide : aucun gain minimal n'est garanti.

Source : [agrégations PyMongo](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/aggregation/).

