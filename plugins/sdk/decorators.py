"""
Plugin SDK Decorators
=====================
Convenience decorators for declaring actions, triggers, and lifecycle hooks
on plugin classes without writing boilerplate manifest code.
"""
from __future__ import annotations
from functools import wraps
from typing import Any, Callable


def action(
    id: str,
    name: str,
    description: str = "",
    idempotent: bool = False,
    readonly: bool = False,
    icon: str = "",
) -> Callable:
    """
    Mark a method as a plugin action.

    Usage::

        @action(id="send_message", name="Send Message")
        def send_message(self, ctx: PluginContext, params: dict) -> ActionResult:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)
        wrapper._is_action   = True          # type: ignore[attr-defined]
        wrapper._action_id   = id            # type: ignore[attr-defined]
        wrapper._action_name = name          # type: ignore[attr-defined]
        wrapper._action_desc = description   # type: ignore[attr-defined]
        wrapper._idempotent  = idempotent    # type: ignore[attr-defined]
        wrapper._readonly    = readonly      # type: ignore[attr-defined]
        wrapper._icon        = icon          # type: ignore[attr-defined]
        return wrapper
    return decorator


def trigger(
    id: str,
    name: str,
    description: str = "",
    icon: str = "",
) -> Callable:
    """
    Mark a method as a plugin trigger poll handler.

    Usage::

        @trigger(id="new_row", name="New Row")
        def on_new_row(self, ctx: PluginContext, since: datetime) -> list[TriggerEvent]:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)
        wrapper._is_trigger   = True         # type: ignore[attr-defined]
        wrapper._trigger_id   = id           # type: ignore[attr-defined]
        wrapper._trigger_name = name         # type: ignore[attr-defined]
        wrapper._trigger_desc = description  # type: ignore[attr-defined]
        wrapper._icon         = icon         # type: ignore[attr-defined]
        return wrapper
    return decorator


def on_install(func: Callable) -> Callable:
    """Mark a method as the install lifecycle hook."""
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)
    wrapper._lifecycle = "install"           # type: ignore[attr-defined]
    return wrapper


def on_uninstall(func: Callable) -> Callable:
    """Mark a method as the uninstall lifecycle hook."""
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)
    wrapper._lifecycle = "uninstall"         # type: ignore[attr-defined]
    return wrapper


def on_configure(func: Callable) -> Callable:
    """Mark a method as the configure lifecycle hook."""
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)
    wrapper._lifecycle = "configure"         # type: ignore[attr-defined]
    return wrapper


def on_enable(func: Callable) -> Callable:
    """Mark a method as the enable lifecycle hook."""
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)
    wrapper._lifecycle = "enable"            # type: ignore[attr-defined]
    return wrapper


def on_disable(func: Callable) -> Callable:
    """Mark a method as the disable lifecycle hook."""
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)
    wrapper._lifecycle = "disable"           # type: ignore[attr-defined]
    return wrapper
