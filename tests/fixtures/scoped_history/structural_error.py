def load(path: str) -> str:
    try:
        return open(path).read()
    except OSError as exc:
        raise RuntimeError(path) from exc
