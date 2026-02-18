"""Application exceptions and global exception handlers."""

from backend.exceptions.base import AppException
from backend.exceptions.handlers import register_exception_handlers

__all__ = ["AppException", "register_exception_handlers"]
