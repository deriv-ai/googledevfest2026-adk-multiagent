"""Accessors for objects stored on app.state (overridable in tests)."""

from __future__ import annotations

from fastapi import Request


def services(request: Request):
    return request.app.state.services


def runtime(request: Request):
    return request.app.state.runtime


def schema_service(request: Request):
    return request.app.state.schema
