# Comprendre AtlasGuard AI et savoir le présenter

## 1. Le problème, en une phrase

« Je construis une chaîne de données et de machine learning qui classe des transactions par risque,
puis je mesure les fraudes trouvées et les fausses alertes sur une période future simulée. »

Le projet utilise des données synthétiques. Tu dois le préciser dès le début : tu présentes une
méthode d'ingénierie et d'évaluation, pas un outil déjà validé dans une banque.

## 2. Suivre le code dans le bon ordre

| Fichier | Question à laquelle il répond |
|---|---|
| `atlasguard/data.py` | Comment créer, vérifier, stocker et lire les transactions ? |
| `atlasguard/model.py` | Comment séparer les périodes, comparer et mesurer ? |
| `atlasguard/pipeline.py` | Dans quel ordre exécuter l'expérience et enregistrer ses résultats ? |
| `dashboard.py` | Comment explorer les erreurs et changer le seuil ? |
| `atlasguard/api.py` | Comment appliquer le même modèle à une nouvelle transaction ? |
| `tests/test_system.py` | Quelles erreurs le projet vérifie automatiquement ? |

Lis d'abord `FEATURES` : montant, heure, distance, tentatives récentes, ancienneté du compte,
transaction internationale, nouvel appareil. Ces informations sont supposées disponibles au moment
de la décision. La cible `is_fraud` sert à apprendre et évaluer ; elle n'entre jamais dans les features.

## 3. La partie Big Data

Un million de lignes n'oblige pas à charger tout le jeu dans pandas. Le générateur écrit des lots
de 25 000 lignes en Parquet. Ce format stocke les données par colonnes et les compresse.
DuckDB lit les partitions, calcule les totaux en SQL et choisit un échantillon déterministe.
La limite `--max-train-rows` contrôle les lignes chargées pour l'apprentissage.

Ce projet fonctionne sur une seule machine : il ne contient pas Spark, Kafka ou un cluster Hadoop.
L'ajout d'un nom de technologie ne prouve pas un passage à l'échelle ; il faut mesurer un vrai besoin.

## 4. La partie IA

On trie les événements chronologiquement : 60 % pour apprendre, 20 % pour choisir, 20 % pour tester.
La régression logistique utilise une standardisation apprise uniquement sur l'entraînement.
Le boosting combine des arbres. Le modèle de référence prédit seulement la fréquence de fraude.

Le gagnant a la meilleure average precision en validation. Son seuil maximise F1 en validation.
Ensuite on le fige et on mesure le test. On ne choisit pas un nouveau gagnant parce qu'il serait
meilleur sur le test : cela utiliserait le test pour prendre une décision d'entraînement.

## 5. Les métriques à savoir expliquer

- **Précision** : parmi les alertes, quelle proportion est réellement frauduleuse ?
- **Rappel** : parmi les fraudes, quelle proportion a été trouvée ?
- **Faux positif** : transaction légitime signalée.
- **Faux négatif** : fraude manquée.
- **Average precision** : qualité du classement des risques sur plusieurs seuils.
- **F1** : compromis entre précision et rappel pour un seuil donné.

Exemple : 10 alertes dont 4 fraudes donnent 40 % de précision. S'il existait 8 fraudes au total,
le rappel est 4 / 8 = 50 %. Une précision élevée seule ne suffit donc pas.

## 6. Démonstration en cinq minutes

1. Montre le schéma du README et explique Parquet puis DuckDB.
2. Ouvre le dashboard et annonce « données synthétiques ».
3. Compare le modèle de référence, la régression logistique et le boosting en validation.
4. Baisse le seuil : observe les alertes, le rappel et les faux positifs.
5. Montre le drift, puis une requête `/predict` et le test de parité API/batch.

Les coûts de l'interface sont hypothétiques. Le PSI compare des distributions, sans prouver que
le modèle est devenu inutilisable. L'importance des variables n'explique pas une causalité.

## 7. Exercices pour vraiment le maîtriser

1. Exécute 10 000 lignes. Retrouve dans `report.json` les tailles des trois périodes.
2. Calcule précision et rappel à la main à partir de TP, FP et FN.
3. Compare deux expériences avec des seeds différentes, sans écraser la première.
4. Explique pourquoi `transaction_id` et `is_fraud` ne sont pas dans `FEATURES`.
5. Trouve une transaction mal classée dans la file de revue et décris ses caractéristiques.
6. Explique pourquoi les scores obtenus ici ne prédisent pas les performances dans une banque.

Quand tu sais répondre à ces six questions, tu peux défendre les choix principaux du projet.
