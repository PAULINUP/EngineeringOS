import json
import logging
import time
import uuid
from datetime import datetime, timezone
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable for holding the trace ID during a request
trace_id_var: ContextVar[str] = ContextVar("trace_id", default=None)

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Build the structured log dictionary
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Inject trace_id if available in the current context
        trace_id = trace_id_var.get()
        if trace_id:
            log_data["trace_id"] = trace_id

        # Add any extra attributes passed via the `extra` arg (skipping standard LogRecord attributes)
        standard_attrs = {
            "args", "asctime", "created", "exc_info", "exc_text", "filename",
            "funcName", "id", "levelname", "levelno", "lineno", "module",
            "msecs", "message", "msg", "name", "pathname", "process",
            "processName", "relativeCreated", "stack_info", "thread",
            "threadName", "taskName", "color_message"
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs:
                log_data[key] = value

        # Include exception traceback if present
        if record.exc_info:
            log_data["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_telemetry():
    """
    Configures the root logger to output JSON structured logs.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicate log entries
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(console_handler)

    # File Handler
    file_handler = logging.FileHandler("system.log", encoding="utf-8")
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger instance with the given name.
    """
    return logging.getLogger(name)


class TelemetryMiddleware(BaseHTTPMiddleware):
    """
    A FastAPI/Starlette middleware that generates a trace ID for each request,
    and logs the start and completion (with latency and status code).
    """
    async def dispatch(self, request: Request, call_next):
        # Generate a new trace ID or use an existing one from headers
        trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
        token = trace_id_var.set(trace_id)
        
        logger = get_logger("telemetry.middleware")
        method = request.method
        url_path = request.url.path

        logger.info("Request started", extra={"method": method, "path": url_path})
        start_time = time.time()

        try:
            response: Response = await call_next(request)
            latency = time.time() - start_time
            logger.info(
                "Request completed",
                extra={
                    "method": method,
                    "path": url_path,
                    "status_code": response.status_code,
                    "latency": latency
                }
            )
            # Attach the trace ID to the response headers
            response.headers["X-Trace-ID"] = trace_id
            return response
        except Exception as e:
            latency = time.time() - start_time
            logger.error(
                f"Request failed with exception: {e}",
                extra={
                    "method": method,
                    "path": url_path,
                    "latency": latency,
                    "status_code": 500
                },
                exc_info=True
            )
            raise
        finally:
            # Reset context variable
            trace_id_var.reset(token)
