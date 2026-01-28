"""
IO Primitives

These primitives connect the pure computation world to the external world.
They use the IO adapter pattern for platform independence.
"""

from typing import Any, Dict, Optional
from primitives import Block, NONE
from io_adapter import get_adapter, Ok, Err, Some


# =============================================================================
# SOURCE PRIMITIVES (data flows IN)
# =============================================================================

class Source:
    """Factory for source primitives"""

    @staticmethod
    def file_read(path: str = None, encoding: str = "utf-8") -> Block:
        """Read file contents"""
        def read_fn(input_path):
            actual_path = path or input_path
            return get_adapter().fs_read(actual_path, encoding)
        return Block(f"source.file.read({path or 'input'})", read_fn)

    @staticmethod
    def file_exists(path: str = None) -> Block:
        """Check if file exists"""
        def exists_fn(input_path):
            actual_path = path or input_path
            return get_adapter().fs_exists(actual_path)
        return Block(f"source.file.exists({path or 'input'})", exists_fn)

    @staticmethod
    def file_list(path: str = None, pattern: str = None) -> Block:
        """List directory contents"""
        def list_fn(input_path):
            actual_path = path or input_path
            return get_adapter().fs_list(actual_path, pattern)
        return Block(f"source.file.list({path or 'input'})", list_fn)

    @staticmethod
    def http_get(url: str = None, headers: Dict = None, timeout: int = 30000) -> Block:
        """HTTP GET request"""
        def get_fn(input_url):
            actual_url = url or input_url
            return get_adapter().http_request("GET", actual_url, headers, None, timeout)
        return Block(f"source.http.get({url or 'input'})", get_fn)

    @staticmethod
    def http_post(url: str = None, headers: Dict = None, timeout: int = 30000) -> Block:
        """HTTP POST request"""
        def post_fn(body):
            actual_url = url or (body.get("url") if isinstance(body, dict) else None)
            actual_body = body.get("body") if isinstance(body, dict) else body
            return get_adapter().http_request("POST", actual_url, headers, actual_body, timeout)
        return Block(f"source.http.post({url or 'input'})", post_fn)

    @staticmethod
    def env(name: str = None, default: str = None) -> Block:
        """Get environment variable"""
        def env_fn(input_name):
            actual_name = name or input_name
            result = get_adapter().env_get(actual_name, default)
            if isinstance(result, Some):
                return result.value
            return NONE
        return Block(f"source.env({name or 'input'})", env_fn)

    @staticmethod
    def env_all() -> Block:
        """Get all environment variables"""
        def env_all_fn(_):
            return get_adapter().env_all()
        return Block("source.env.all()", env_all_fn)

    @staticmethod
    def time_now() -> Block:
        """Get current timestamp"""
        def now_fn(_):
            return get_adapter().time_now()
        return Block("source.time.now()", now_fn)

    @staticmethod
    def random(min_val: float = 0, max_val: float = 1) -> Block:
        """Get random number"""
        def random_fn(_):
            return get_adapter().random_number(min_val, max_val)
        return Block(f"source.random({min_val}, {max_val})", random_fn)

    @staticmethod
    def uuid() -> Block:
        """Get random UUID"""
        def uuid_fn(_):
            return get_adapter().random_uuid()
        return Block("source.uuid()", uuid_fn)

    @staticmethod
    def stdin(prompt: str = None) -> Block:
        """Read from stdin"""
        def stdin_fn(_):
            return get_adapter().stdin(prompt)
        return Block(f"source.stdin({prompt!r})", stdin_fn)

    @staticmethod
    def args() -> Block:
        """Get command-line arguments"""
        def args_fn(_):
            return get_adapter().args()
        return Block("source.args()", args_fn)


# =============================================================================
# SINK PRIMITIVES (data flows OUT)
# =============================================================================

class Sink:
    """Factory for sink primitives"""

    @staticmethod
    def file_write(path: str = None, mode: str = "overwrite") -> Block:
        """Write to file"""
        def write_fn(input_):
            if isinstance(input_, dict):
                actual_path = path or input_.get("path")
                content = input_.get("content", "")
            else:
                actual_path = path
                content = str(input_)
            return get_adapter().fs_write(actual_path, content, mode)
        return Block(f"sink.file.write({path or 'input'})", write_fn)

    @staticmethod
    def file_append(path: str = None) -> Block:
        """Append to file"""
        return Sink.file_write(path, mode="append")

    @staticmethod
    def file_delete(path: str = None) -> Block:
        """Delete file"""
        def delete_fn(input_path):
            actual_path = path or input_path
            return get_adapter().fs_delete(actual_path)
        return Block(f"sink.file.delete({path or 'input'})", delete_fn)

    @staticmethod
    def stdout(newline: bool = True) -> Block:
        """Write to stdout"""
        def stdout_fn(text):
            get_adapter().stdout(str(text), newline)
            return NONE
        return Block("sink.stdout()", stdout_fn)

    @staticmethod
    def stderr() -> Block:
        """Write to stderr"""
        def stderr_fn(text):
            get_adapter().stderr(str(text))
            return NONE
        return Block("sink.stderr()", stderr_fn)

    @staticmethod
    def log(level: str = "info") -> Block:
        """Write log entry"""
        def log_fn(input_):
            if isinstance(input_, dict):
                message = input_.get("message", str(input_))
                data = {k: v for k, v in input_.items() if k != "message"}
            else:
                message = str(input_)
                data = None
            get_adapter().log(level, message, data if data else None)
            return NONE
        return Block(f"sink.log({level})", log_fn)


# =============================================================================
# CONVENIENCE CONSTRUCTORS
# =============================================================================

# Sources
file_read = Source.file_read
file_exists = Source.file_exists
file_list = Source.file_list
http_get = Source.http_get
http_post = Source.http_post
env = Source.env
env_all = Source.env_all
time_now = Source.time_now
random = Source.random
uuid = Source.uuid
stdin = Source.stdin
args = Source.args

# Sinks
file_write = Sink.file_write
file_append = Sink.file_append
file_delete = Sink.file_delete
stdout = Sink.stdout
stderr = Sink.stderr
log = Sink.log


# =============================================================================
# RESULT HANDLING PRIMITIVES
# =============================================================================

def unwrap() -> Block:
    """Unwrap Result, raising on error"""
    def unwrap_fn(result):
        if isinstance(result, Ok):
            return result.value
        elif isinstance(result, Err):
            raise Exception(f"Unwrap failed: {result.error}")
        return result
    return Block("unwrap()", unwrap_fn)


def unwrap_or(default: Any) -> Block:
    """Unwrap Result, returning default on error"""
    def unwrap_or_fn(result):
        if isinstance(result, Ok):
            return result.value
        elif isinstance(result, Err):
            return default
        return result
    return Block(f"unwrap_or({default!r})", unwrap_or_fn)


def map_ok(fn_expr: str) -> Block:
    """Transform Ok value, pass through Err"""
    from primitives import parse_expr
    fn = parse_expr(fn_expr)
    def map_ok_fn(result):
        if isinstance(result, Ok):
            return Ok(fn(result.value))
        return result
    return Block(f"map_ok({fn_expr})", map_ok_fn)


def map_err(fn_expr: str) -> Block:
    """Transform Err value, pass through Ok"""
    from primitives import parse_expr
    fn = parse_expr(fn_expr)
    def map_err_fn(result):
        if isinstance(result, Err):
            return Err(fn(result.error))
        return result
    return Block(f"map_err({fn_expr})", map_err_fn)


def is_ok() -> Block:
    """Check if Result is Ok"""
    def is_ok_fn(result):
        return isinstance(result, Ok)
    return Block("is_ok()", is_ok_fn)


def is_err() -> Block:
    """Check if Result is Err"""
    def is_err_fn(result):
        return isinstance(result, Err)
    return Block("is_err()", is_err_fn)
