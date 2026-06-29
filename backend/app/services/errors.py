"""Error sanitization helpers.

Internal exception details (raw message, stack, file paths, library internals)
must never reach clients. These helpers wrap the boundary where a caught
exception becomes a user-facing message: they log the full exception server-side
(correlated with task/project ids for support) and return a short, generic,
localized message.

Keep the generic messages stable so the frontend can show them verbatim.
"""

import logging

logger = logging.getLogger(__name__)

# Generic, user-facing failure messages. These intentionally reveal nothing
# about the underlying cause.
GENERIC_PIPELINE_ERROR = "生成失败，请稍后重试。"
GENERIC_PLAY_ERROR = "回合执行失败，请稍后重试。"


def log_pipeline_error(exc: BaseException, *, task_id=None, project_id=None) -> str:
    """Log the full pipeline exception server-side and return a generic message.

    The returned string is safe to persist on ``Task.error_msg`` / surface via
    ``/progress``. The original exception (message + traceback) is written to
    the server log, correlated with task_id / project_id when available.
    """
    logger.error(
        "Pipeline failed (task_id=%s, project_id=%s): %r",
        task_id, project_id, exc,
        exc_info=True,
    )
    return GENERIC_PIPELINE_ERROR


def log_play_error(exc: BaseException, *, project_id=None) -> str:
    """Log the full play_world turn exception server-side and return a generic message.

    The returned string is safe to put in an HTTP 500 detail. The original
    exception is written to the server log, correlated with project_id.
    """
    logger.error(
        "World turn failed (project_id=%s): %r",
        project_id, exc,
        exc_info=True,
    )
    return GENERIC_PLAY_ERROR
