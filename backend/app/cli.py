"""Small CLI: `python -m app.cli train | reindex | seed`"""
import json
import sys

from .services import ml


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "train":
        print(json.dumps(ml.train(), indent=2))
    elif cmd == "reindex":
        from .services.rag import get_knowledge_base

        print(f"indexed {get_knowledge_base().index(force=True)} chunks")
    elif cmd == "seed":
        from .seed import seed_default_fields

        seed_default_fields()
        print("seeded default dynamic fields")
    else:
        print("usage: python -m app.cli [train|reindex|seed]")
        sys.exit(1)


if __name__ == "__main__":
    main()
