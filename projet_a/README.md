# A — Jeu de quiz Redis

Les missions sont dans [quiz.redis](quiz.redis), en commandes Redis.
Le petit lanceur Python est facultatif : il affiche les commandes et leurs résultats.
Toutes les commandes de préparation réinitialisent les clés connues de cette démonstration,
y compris les six profils joueurs, pour éviter qu'un ancien champ ou type de clé perturbe le résultat.
Utiliser le serveur dédié redis-quiz, pas une base contenant vos vraies données.

Depuis la racine du dépôt, après installation et démarrage décrits dans le README principal :

```powershell
python -m projet_a.executer --reinitialiser-demo
```

Pour travailler uniquement en Redis, ouvrir `docker compose exec redis-quiz redis-cli`
et copier les commandes de quiz.redis mission par mission. Redis 6.2 minimum.

## Vérification attendue

| Joueur | Points | Parties |
|---|---:|---:|
| Ilyas (j2) | 73 | 2 |
| Nour (j1) | 55 | 2 |
| Adam (j4) | 46 | 2 |
| Sara (j3) | 43 | 2 |
| Yanis (j6) | 15 | 1 |
| Lina (j5) | 8 | 1 |

5 parties au total. Sara : rang Redis 3, soit 4e place (index à partir de zéro).
Entre 40 et 60 points : Sara, Adam et Nour.
Première victoire : j1, j2, j3, j4. Rapide : j2, j5, j3.
Invaincu : j2. Sans badge : j6.

## Expiration et persistance

Après la mission 3, attendre au moins 15 secondes et vérifier :
```powershell
docker compose exec redis-quiz redis-cli EXISTS session:test:active
```
Résultat attendu : 0. Une session n'est prolongée que par un EXPIRE explicite à chaque activité.
Les valeurs de session du sujet sont des marqueurs de démo, pas des jetons d'authentification.

Exécuter les commandes de [persistance.redis](persistance.redis) dans redis-cli.
Attendre la fin du BGSAVE, puis :
```powershell
docker compose restart redis-quiz
docker compose exec redis-quiz redis-cli ZREVRANGE classement:general:points 0 -1 WITHSCORES
docker compose exec redis-quiz redis-cli HGETALL joueur:j4:profil
docker compose exec redis-quiz redis-cli SMEMBERS badge:invaincu:joueurs
```
Le volume Docker quiz_data conserve AOF/RDB lors de la recréation du conteneur.
`docker compose down` garde les volumes ; `down -v` les supprime.
Le classement est une donnée principale : le serveur est configuré noeviction.
Les badges sont ceux des cinq parties fixes ; ils ne sont pas recalculés automatiquement pour des parties ajoutées à la main.

Sources : [ZRANGE BYSCORE](https://redis.io/docs/latest/commands/zrange/),
[persistance Redis](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/).

