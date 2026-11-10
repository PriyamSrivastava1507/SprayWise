from pathlib import Path


class LocalStorageClient:
    """Stores files on local disk within a specified root directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        resolved = (self.root / key).resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError("bad storage key")
        return resolved

    def save(self, key: str, data: bytes) -> str:
        target_path = self._path(key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(data)
        return key

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def url(self, key: str) -> str:
        # Validate that the key resolves safely inside storage root
        self._path(key)
        # Normalize Windows backslashes to forward slashes for URL paths
        normalized_key = key.replace("\\", "/").lstrip("/")
        return f"/media/{normalized_key}"

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

