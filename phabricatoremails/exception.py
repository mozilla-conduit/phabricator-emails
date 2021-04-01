import traceback


def render_exception(e: Exception):
    return "".join(traceback.format_exception(type(e), e, e.__traceback__))
