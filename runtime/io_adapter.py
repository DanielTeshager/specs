"""
IO Adapter Implementation

Provides both Mock (for testing) and Real (for production) adapters.
The same primitive specs work with either adapter.
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import os
import json


# =============================================================================
# RESULT TYPES
# =============================================================================

@dataclass
class Ok:
    """Success result"""
    value: Any

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> Any:
        return self.value

    def __repr__(self):
        return f"Ok({self.value!r})"


@dataclass
class Err:
    """Error result"""
    error: "IOError"

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> Any:
        raise Exception(f"Called unwrap on Err: {self.error}")

    def __repr__(self):
        return f"Err({self.error!r})"


@dataclass
class IOError:
    """IO Error type"""
    type: str  # NotFound, PermissionDenied, Timeout, etc.
    message: Optional[str] = None
    path: Optional[str] = None

    def __repr__(self):
        parts = [self.type]
        if self.path:
            parts.append(f"path={self.path}")
        if self.message:
            parts.append(f"msg={self.message}")
        return f"IOError({', '.join(parts)})"


@dataclass
class Some:
    """Optional value present"""
    value: Any

    def is_some(self) -> bool:
        return True

    def is_none(self) -> bool:
        return False

    def unwrap(self) -> Any:
        return self.value


class NoneType:
    """Optional value absent"""
    def is_some(self) -> bool:
        return False

    def is_none(self) -> bool:
        return True

    def unwrap_or(self, default: Any) -> Any:
        return default

NONE = NoneType()


# =============================================================================
# ADAPTER INTERFACE
# =============================================================================

class IOAdapter(ABC):
    """Abstract base for IO adapters"""

    # File system
    @abstractmethod
    def fs_read(self, path: str, encoding: str = "utf-8") -> Ok | Err:
        pass

    @abstractmethod
    def fs_write(self, path: str, content: str, mode: str = "overwrite") -> Ok | Err:
        pass

    @abstractmethod
    def fs_exists(self, path: str) -> bool:
        pass

    @abstractmethod
    def fs_delete(self, path: str) -> Ok | Err:
        pass

    @abstractmethod
    def fs_list(self, path: str, pattern: Optional[str] = None) -> Ok | Err:
        pass

    # HTTP
    @abstractmethod
    def http_request(self, method: str, url: str, headers: Dict = None,
                     body: Any = None, timeout: int = 30000) -> Ok | Err:
        pass

    # Environment
    @abstractmethod
    def env_get(self, name: str, default: Optional[str] = None) -> Some | NoneType:
        pass

    @abstractmethod
    def env_all(self) -> Dict[str, str]:
        pass

    # Time
    @abstractmethod
    def time_now(self) -> int:
        pass

    # Random
    @abstractmethod
    def random_number(self, min_val: float = 0, max_val: float = 1) -> float:
        pass

    @abstractmethod
    def random_uuid(self) -> str:
        pass

    # Console
    @abstractmethod
    def stdout(self, text: str, newline: bool = True) -> None:
        pass

    @abstractmethod
    def stderr(self, text: str) -> None:
        pass

    @abstractmethod
    def stdin(self, prompt: Optional[str] = None) -> Ok | Err:
        pass

    # Process
    @abstractmethod
    def args(self) -> List[str]:
        pass

    # Logging
    @abstractmethod
    def log(self, level: str, message: str, data: Optional[Dict] = None) -> None:
        pass


# =============================================================================
# MOCK ADAPTER (for testing)
# =============================================================================

class MockAdapter(IOAdapter):
    """
    In-memory mock adapter for testing.
    All IO is simulated using dictionaries.
    """

    def __init__(self):
        # Mock state
        self.fs: Dict[str, str] = {}
        self.http_responses: Dict[str, Dict] = {}
        self.env: Dict[str, str] = {}
        self.time: int = 0
        self.random_values: List[float] = []
        self.random_index: int = 0
        self.stdin_buffer: str = ""
        self.argv: List[str] = []

        # Capture state (for verification)
        self.stdout_buffer: str = ""
        self.stderr_buffer: str = ""
        self.log_entries: List[Dict] = []
        self.http_requests: List[Dict] = []

    def setup(self, **kwargs):
        """Configure mock state"""
        if "mock_fs" in kwargs:
            self.fs = dict(kwargs["mock_fs"])
        if "mock_http" in kwargs:
            self.http_responses = dict(kwargs["mock_http"])
        if "mock_env" in kwargs:
            self.env = dict(kwargs["mock_env"])
        if "mock_time" in kwargs:
            self.time = kwargs["mock_time"]
        if "mock_random" in kwargs:
            self.random_values = list(kwargs["mock_random"])
            self.random_index = 0
        if "mock_stdin" in kwargs:
            self.stdin_buffer = kwargs["mock_stdin"]
        if "mock_args" in kwargs:
            self.argv = list(kwargs["mock_args"])
        return self

    def reset_captures(self):
        """Clear captured output"""
        self.stdout_buffer = ""
        self.stderr_buffer = ""
        self.log_entries = []
        self.http_requests = []

    # --- File System ---

    def fs_read(self, path: str, encoding: str = "utf-8") -> Ok | Err:
        path = self._normalize_path(path)
        if path in self.fs:
            return Ok(self.fs[path])
        return Err(IOError("NotFound", path=path))

    def fs_write(self, path: str, content: str, mode: str = "overwrite") -> Ok | Err:
        path = self._normalize_path(path)

        if mode == "create_new" and path in self.fs:
            return Err(IOError("AlreadyExists", path=path))

        if mode == "append" and path in self.fs:
            self.fs[path] = self.fs[path] + content
        else:
            self.fs[path] = content

        return Ok(None)

    def fs_exists(self, path: str) -> bool:
        path = self._normalize_path(path)
        return path in self.fs

    def fs_delete(self, path: str) -> Ok | Err:
        path = self._normalize_path(path)
        if path in self.fs:
            del self.fs[path]
            return Ok(None)
        return Err(IOError("NotFound", path=path))

    def fs_list(self, path: str, pattern: Optional[str] = None) -> Ok | Err:
        path = self._normalize_path(path)
        if not path.endswith("/"):
            path += "/"

        entries = []
        seen = set()
        for file_path in self.fs:
            if file_path.startswith(path):
                remainder = file_path[len(path):]
                if "/" in remainder:
                    name = remainder.split("/")[0]
                    entry_type = "directory"
                else:
                    name = remainder
                    entry_type = "file"

                if name and name not in seen:
                    if pattern is None or self._matches_glob(name, pattern):
                        entries.append({"name": name, "type": entry_type})
                        seen.add(name)

        return Ok(entries)

    def _normalize_path(self, path: str) -> str:
        """Normalize path separators"""
        return path.replace("\\", "/").strip("/")

    def _matches_glob(self, name: str, pattern: str) -> bool:
        """Simple glob matching (*.txt style)"""
        if pattern == "*":
            return True
        if pattern.startswith("*."):
            return name.endswith(pattern[1:])
        return name == pattern

    # --- HTTP ---

    def http_request(self, method: str, url: str, headers: Dict = None,
                     body: Any = None, timeout: int = 30000) -> Ok | Err:
        self.http_requests.append({
            "method": method,
            "url": url,
            "headers": headers,
            "body": body
        })

        if url in self.http_responses:
            mock = self.http_responses[url]
            return Ok({
                "status": mock.get("status", 200),
                "headers": mock.get("headers", {}),
                "body": mock.get("body", "")
            })

        return Err(IOError("ConnectionFailed", message=f"No mock for {url}"))

    # --- Environment ---

    def env_get(self, name: str, default: Optional[str] = None) -> Some | NoneType:
        if name in self.env:
            return Some(self.env[name])
        if default is not None:
            return Some(default)
        return NONE

    def env_all(self) -> Dict[str, str]:
        return dict(self.env)

    # --- Time ---

    def time_now(self) -> int:
        return self.time

    # --- Random ---

    def random_number(self, min_val: float = 0, max_val: float = 1) -> float:
        if self.random_index < len(self.random_values):
            base = self.random_values[self.random_index]
            self.random_index += 1
        else:
            base = 0.5

        return min_val + base * (max_val - min_val)

    def random_uuid(self) -> str:
        return "00000000-0000-4000-8000-000000000000"

    # --- Console ---

    def stdout(self, text: str, newline: bool = True) -> None:
        self.stdout_buffer += text
        if newline:
            self.stdout_buffer += "\n"

    def stderr(self, text: str) -> None:
        self.stderr_buffer += text + "\n"

    def stdin(self, prompt: Optional[str] = None) -> Ok | Err:
        if prompt:
            self.stdout(prompt, newline=False)
        return Ok(self.stdin_buffer)

    # --- Process ---

    def args(self) -> List[str]:
        return list(self.argv)

    # --- Logging ---

    def log(self, level: str, message: str, data: Optional[Dict] = None) -> None:
        entry = {"level": level, "message": message}
        if data:
            entry["data"] = data
        self.log_entries.append(entry)


# =============================================================================
# REAL ADAPTER (for production)
# =============================================================================

class RealAdapter(IOAdapter):
    """
    Real IO adapter using actual system calls.
    """

    # --- File System ---

    def fs_read(self, path: str, encoding: str = "utf-8") -> Ok | Err:
        try:
            with open(path, "r", encoding=encoding) as f:
                return Ok(f.read())
        except FileNotFoundError:
            return Err(IOError("NotFound", path=path))
        except PermissionError:
            return Err(IOError("PermissionDenied", path=path))
        except Exception as e:
            return Err(IOError("Unknown", message=str(e)))

    def fs_write(self, path: str, content: str, mode: str = "overwrite") -> Ok | Err:
        try:
            # Create parent directories
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)

            if mode == "create_new" and os.path.exists(path):
                return Err(IOError("AlreadyExists", path=path))

            file_mode = "a" if mode == "append" else "w"
            with open(path, file_mode, encoding="utf-8") as f:
                f.write(content)
            return Ok(None)
        except PermissionError:
            return Err(IOError("PermissionDenied", path=path))
        except Exception as e:
            return Err(IOError("Unknown", message=str(e)))

    def fs_exists(self, path: str) -> bool:
        return os.path.exists(path)

    def fs_delete(self, path: str) -> Ok | Err:
        try:
            if os.path.isfile(path):
                os.remove(path)
            else:
                os.rmdir(path)
            return Ok(None)
        except FileNotFoundError:
            return Err(IOError("NotFound", path=path))
        except OSError as e:
            if "not empty" in str(e).lower():
                return Err(IOError("DirectoryNotEmpty", path=path))
            return Err(IOError("Unknown", message=str(e)))

    def fs_list(self, path: str, pattern: Optional[str] = None) -> Ok | Err:
        try:
            entries = []
            for name in os.listdir(path):
                if pattern and not self._matches_glob(name, pattern):
                    continue
                full_path = os.path.join(path, name)
                entry_type = "directory" if os.path.isdir(full_path) else "file"
                entries.append({"name": name, "type": entry_type})
            return Ok(entries)
        except FileNotFoundError:
            return Err(IOError("NotFound", path=path))
        except Exception as e:
            return Err(IOError("Unknown", message=str(e)))

    def _matches_glob(self, name: str, pattern: str) -> bool:
        if pattern == "*":
            return True
        if pattern.startswith("*."):
            return name.endswith(pattern[1:])
        return name == pattern

    # --- HTTP ---

    def http_request(self, method: str, url: str, headers: Dict = None,
                     body: Any = None, timeout: int = 30000) -> Ok | Err:
        try:
            import urllib.request
            import urllib.error

            req = urllib.request.Request(url, method=method)

            if headers:
                for k, v in headers.items():
                    req.add_header(k, v)

            if body:
                if isinstance(body, dict):
                    body = json.dumps(body).encode("utf-8")
                    req.add_header("Content-Type", "application/json")
                elif isinstance(body, str):
                    body = body.encode("utf-8")
                req.data = body

            timeout_sec = timeout / 1000
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                return Ok({
                    "status": resp.status,
                    "headers": dict(resp.headers),
                    "body": resp.read().decode("utf-8")
                })

        except urllib.error.HTTPError as e:
            return Ok({
                "status": e.code,
                "headers": dict(e.headers),
                "body": e.read().decode("utf-8")
            })
        except urllib.error.URLError as e:
            if "timed out" in str(e):
                return Err(IOError("Timeout", message=url))
            return Err(IOError("ConnectionFailed", message=str(e)))
        except Exception as e:
            return Err(IOError("Unknown", message=str(e)))

    # --- Environment ---

    def env_get(self, name: str, default: Optional[str] = None) -> Some | NoneType:
        value = os.environ.get(name, default)
        if value is not None:
            return Some(value)
        return NONE

    def env_all(self) -> Dict[str, str]:
        return dict(os.environ)

    # --- Time ---

    def time_now(self) -> int:
        import time
        return int(time.time() * 1000)

    # --- Random ---

    def random_number(self, min_val: float = 0, max_val: float = 1) -> float:
        import random
        return random.uniform(min_val, max_val)

    def random_uuid(self) -> str:
        import uuid
        return str(uuid.uuid4())

    # --- Console ---

    def stdout(self, text: str, newline: bool = True) -> None:
        import sys
        sys.stdout.write(text)
        if newline:
            sys.stdout.write("\n")
        sys.stdout.flush()

    def stderr(self, text: str) -> None:
        import sys
        sys.stderr.write(text + "\n")
        sys.stderr.flush()

    def stdin(self, prompt: Optional[str] = None) -> Ok | Err:
        try:
            if prompt:
                self.stdout(prompt, newline=False)
            line = input()
            return Ok(line)
        except EOFError:
            return Err(IOError("InvalidData", message="EOF"))
        except Exception as e:
            return Err(IOError("Unknown", message=str(e)))

    # --- Process ---

    def args(self) -> List[str]:
        import sys
        return sys.argv[1:]

    # --- Logging ---

    def log(self, level: str, message: str, data: Optional[Dict] = None) -> None:
        import sys
        import json
        entry = {"level": level, "message": message}
        if data:
            entry["data"] = data
        sys.stderr.write(json.dumps(entry) + "\n")


# =============================================================================
# GLOBAL ADAPTER (can be swapped)
# =============================================================================

_current_adapter: IOAdapter = RealAdapter()


def set_adapter(adapter: IOAdapter) -> None:
    """Set the global IO adapter"""
    global _current_adapter
    _current_adapter = adapter


def get_adapter() -> IOAdapter:
    """Get the current IO adapter"""
    return _current_adapter


def use_mock(**setup) -> MockAdapter:
    """Switch to mock adapter with optional setup"""
    mock = MockAdapter()
    mock.setup(**setup)
    set_adapter(mock)
    return mock


def use_real() -> RealAdapter:
    """Switch to real adapter"""
    real = RealAdapter()
    set_adapter(real)
    return real
