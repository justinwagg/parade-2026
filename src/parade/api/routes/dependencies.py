from fastapi import Request
from parade.api.context import AppContext


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx
