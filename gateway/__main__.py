"""Start the mode selected in gateway/.env with python -m gateway."""

import os
import argparse

from .config import load_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("local", "mqtt"))
    parser.add_argument("--env-file")
    parser.add_argument("--db")
    parser.add_argument("--port", type=int)
    parser.add_argument("--bind")
    args = parser.parse_args()
    for name, value in (
        ("PILLBOX_MODE", args.mode),
        ("PILLBOX_ENV_FILE", args.env_file),
        ("PILLBOX_DB", args.db),
        ("PORT", args.port),
        ("PILLBOX_BIND", args.bind),
    ):
        if value is not None:
            os.environ[name] = str(value)
    load_environment()
    mode = os.getenv("PILLBOX_MODE", "local")
    if mode == "local":
        from .local_system import main as run

        run([])
    elif mode == "mqtt":
        from .app import main as run

        run()
    else:
        raise ValueError("PILLBOX_MODE must be local or mqtt")


if __name__ == "__main__":
    main()
