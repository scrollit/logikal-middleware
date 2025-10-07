# -*- coding: utf-8 -*-

import logging

_logger = logging.getLogger(__name__)


class MBIOEError(Exception):
    """Base exception for MBIOE operations"""
    def __init__(self, message, context=None):
        self.context = context or {}
        super().__init__(message)
        _logger.error(f"MBIOE Error: {message}", extra=self.context)


class APIConnectionError(MBIOEError):
    """API connection issues"""
    pass


class AuthenticationError(MBIOEError):
    """Authentication failures"""
    pass


class SessionError(MBIOEError):
    """Session management errors"""
    pass


class ConfigurationError(MBIOEError):
    """Configuration validation errors"""
    pass
