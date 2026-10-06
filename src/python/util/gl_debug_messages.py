import logging

from OpenGL.GL import *
from OpenGL.GL.ARB.debug_output import GLDEBUGPROC

_debug_callback_ref = None
logger = logging.getLogger(__name__)


def enable_gl_debug_messages(
        synchronous=True,
        ignore_notifications=True,
        print_ids=False,
):
    global _debug_callback_ref

    SOURCE = {
        GL_DEBUG_SOURCE_API: "API",
        GL_DEBUG_SOURCE_WINDOW_SYSTEM: "WINDOW",
        GL_DEBUG_SOURCE_SHADER_COMPILER: "SHADER",
        GL_DEBUG_SOURCE_THIRD_PARTY: "3RD_PARTY",
        GL_DEBUG_SOURCE_APPLICATION: "APP",
        GL_DEBUG_SOURCE_OTHER: "OTHER",
    }

    TYPE = {
        GL_DEBUG_TYPE_ERROR: "ERROR",
        GL_DEBUG_TYPE_DEPRECATED_BEHAVIOR: "DEPRECATED",
        GL_DEBUG_TYPE_UNDEFINED_BEHAVIOR: "UNDEFINED",
        GL_DEBUG_TYPE_PORTABILITY: "PORTABILITY",
        GL_DEBUG_TYPE_PERFORMANCE: "PERFORMANCE",
        GL_DEBUG_TYPE_MARKER: "MARKER",
        GL_DEBUG_TYPE_PUSH_GROUP: "PUSH",
        GL_DEBUG_TYPE_POP_GROUP: "POP",
        GL_DEBUG_TYPE_OTHER: "OTHER",
    }

    SEVERITY = {
        GL_DEBUG_SEVERITY_HIGH: "HIGH",
        GL_DEBUG_SEVERITY_MEDIUM: "MEDIUM",
        GL_DEBUG_SEVERITY_LOW: "LOW",
        GL_DEBUG_SEVERITY_NOTIFICATION: "NOTIFY",
    }

    def _callback(source, type, id, severity, length, message, userParam):
        src = SOURCE.get(source, "UNKNOWN")
        typ = TYPE.get(type, "UNKNOWN")
        sev = SEVERITY.get(severity, "UNKNOWN")
        msg = message.decode("utf-8", errors="replace")

        if print_ids:
            logger.error("[GL %s] (%s/%s) id=%s: %s", sev, src, typ, id, msg)
        else:
            logger.error("[GL %s] (%s/%s): %s", sev, src, typ, msg)

    _debug_callback_ref = GLDEBUGPROC(_callback)

    glEnable(GL_DEBUG_OUTPUT)
    if synchronous:
        glEnable(GL_DEBUG_OUTPUT_SYNCHRONOUS)

    glDebugMessageCallback(_debug_callback_ref, None)

    if ignore_notifications:
        glDebugMessageControl(
            GL_DONT_CARE,
            GL_DONT_CARE,
            GL_DEBUG_SEVERITY_NOTIFICATION,
            0,
            None,
            GL_FALSE,
        )
