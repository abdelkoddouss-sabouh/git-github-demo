# Featured project: AtlasGuard AI

[Explore AtlasGuard AI](atlasguard-ai/) — a million-row synthetic transaction lake, explainable machine learning, an interactive dashboard and a prediction API. Includes measured results and a French learning guide.

---

# Projets Redis — Cache MongoDB et quiz

Deux implémentations pédagogiques des sujets de cours, avec code et instructions de lancement.

- [Projet B1 : cache Redis devant MongoDB](projet_b1/)
- [Projet A : jeu de quiz en commandes Redis](projet_a/)

## Démarrage (Windows PowerShell, Python 3.10+ et Docker Compose)

```powershell
git clone https://github.com/abdelkoddouss-sabouh/git-github-demo.git
cd git-github-demo
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
docker compose up -d
docker compose exec mongo mongosh --quiet --eval "db.runCommand({ping:1})"
docker compose exec redis-cache redis-cli ping
docker compose exec redis-quiz redis-cli ping
.\.venv\Scripts\python.exe -m projet_b1.generer
.\.venv\Scripts\python.exe -m projet_b1.demo
.\.venv\Scripts\python.exe -m projet_a.executer --reinitialiser-demo
```

Attendre que les trois vérifications répondent avant les scripts Python.
Sous Linux/macOS, remplacer .\.venv\Scripts\python.exe par .venv/bin/python.
Les ports locaux 27018, 6380 et 6381 évitent les ports habituels des installations de cours.
Les services écoutent uniquement sur localhost ; cette configuration est pour un TP local.

B1 génère des données **synthétiques** (le script du professeur n'est pas inclus).
Les projets utilisent deux serveurs Redis séparés : cache temporaire et données persistantes du quiz.
Pour arrêter : `docker compose down` (conserve les volumes).

## Tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Les tests unitaires utilisent fakeredis/mongomock. Ils ne valident ni les performances,
ni la persistance réelle après redémarrage : suivre les commandes des README sur Docker
pour ces vérifications. Aucun compte rendu ou présentation n'est inclus.
