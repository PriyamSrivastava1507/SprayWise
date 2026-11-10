import os
from pathlib import Path


class LocalStorageClient:
    """Stores files on local disk within a specified root directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        """Resolve a key to a path guaranteed to stay inside the root.

        Rejects ``../`` and absolute keys, and the root itself (empty key or ``.``).
        """
        resolved = (self.root / key).resolve()
        if resolved == self.root or not resolved.is_relative_to(self.root):
            raise ValueError("bad storage key")
        return resolved

    def save(self, key: str, data: bytes) -> str:
        target_path = self._path(key)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Write then rename, so a crash never leaves a half-written file.
        temp_path = target_path.with_name(target_path.name + ".tmp")
        temp_path.write_bytes(data)
        os.replace(temp_path, target_path)
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
        path = self._path(key)
        path.unlink(missing_ok=True)

        # Remove the per-scan folder once it is empty (never the root itself).
        parent = path.parent
        while parent != self.root:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
