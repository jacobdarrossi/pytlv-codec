"""Exception hierarchy for pytlv-codec.

All custom exceptions inherit from PytlvError. Where appropriate, they also
inherit from a built-in (ValueError, NotImplementedError) so that existing
generic handlers continue to work.
"""

from __future__ import annotations


class PytlvError(Exception):
    """Base exception for all pytlv-codec errors."""


class InvalidTLVError(PytlvError, ValueError):
    """Raised when a TLV/LTV stream is malformed during decode.

    Examples: truncated data, invalid length field, duplicate tags
    when not allowed.
    """


class EncodingError(PytlvError, ValueError):
    """Raised when input data cannot be encoded.

    Examples: tag with wrong size, empty value when not allowed,
    value too long to fit in the configured length_size.
    """


class UnsupportedConfigError(PytlvError, NotImplementedError):
    """Raised when the codec configuration uses a combination not yet implemented."""
