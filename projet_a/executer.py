"""Exécute les commandes Redis du sujet, après confirmation explicite du reset."""
import argparse
from pathlib import Path
import os
import shlex
import redis

COMMANDES = Path(__file__).with_name("quiz.redis")


def executer(client, afficher=True):
    transaction = None
    try:
        for ligne in COMMANDES.read_text(encoding="utf-8").splitlines():
            args = shlex.split(ligne, comments=True)
            if not args:
                continue
            if args[0] == "MULTI":
                transaction = client.pipeline(transaction=True)
            elif args[0] == "EXEC":
                resultat = transaction.execute()
                transaction = None
                if afficher:
                    print("EXEC ->", resultat)
            elif transaction is not None:
                transaction.execute_command(*args)
            else:
                resultat = client.execute_command(*args)
                if afficher:
                    print(ligne, "->", resultat)
        if transaction is not None:
            raise ValueError("Transaction MULTI incomplète : EXEC manquant.")
    finally:
        if transaction is not None:
            transaction.reset()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reinitialiser-demo", action="store_true")
    args = parser.parse_args()
    if not args.reinitialiser_demo:
        parser.error("Ajouter --reinitialiser-demo : les données des missions seront réinitialisées.")
    client = redis.Redis.from_url(os.getenv("REDIS_QUIZ_URL", "redis://localhost:6381/0"),
                                  decode_responses=True, socket_timeout=3)
    client.ping()
    executer(client)


if __name__ == "__main__":
    main()
