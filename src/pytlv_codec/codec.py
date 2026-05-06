"""Codec for encoding and decoding TLV/LTV streams.

This is the v0.1.0 minimal implementation — supports only the default
configuration (TLV order, ASCII everywhere, length counts bytes-on-wire,
length_includes_tag=False). Other configurations raise UnsupportedConfigError
until implemented in subsequent versions.
"""

from __future__ import annotations

import string

from pytlv_codec.config import (
    CodecConfig,
    Encoding,
    Order,
    ValueType,
)
from pytlv_codec.exceptions import (
    EncodingError,
    InvalidTLVError,
    UnsupportedConfigError,
)


class Codec:
    """Encode and decode dict ↔ TLV/LTV string."""

    def __init__(self, config: CodecConfig | None = None) -> None:
        self.config = config or CodecConfig()

    # -- Public API ------------------------------------------------------

    def encode(self, data: dict[str, str]) -> str:
        """Encode a dict of {tag: value} pairs into a TLV/LTV string."""
        self._guard_supported()

        parts: list[str] = []

        for tag, value in data.items():
            self._validate_tag(tag)
            self._validate_value(value)

            length = self._compute_length(value)
            length_str = self._format_length(length)

            parts.append(tag + length_str + value)

        return "".join(parts)

    def decode(self, encoded: str) -> dict[str, str]:
        """Decode a TLV/LTV string back into a dict of {tag: value} pairs."""
        self._guard_supported()

        cfg = self.config
        result: dict[str, str] = {}
        pos = 0

        while pos < len(encoded):
            tag, pos = self._read_field(encoded, pos, cfg.tag_size, "tag")
            self._validate_tag_alphabet(tag)
            length_str, pos = self._read_field(encoded, pos, cfg.length_size, "length")

            try:
                length = int(length_str)
            except ValueError as exc:
                raise InvalidTLVError(
                    f"Invalid length {length_str!r} at position {pos - cfg.length_size}"
                ) from exc

            value, pos = self._read_field(encoded, pos, length, "value")

            if tag in result and not cfg.allow_duplicate_tags:
                raise InvalidTLVError(f"Duplicate tag {tag!r} not allowed")

            result[tag] = value

        return result

    # -- Internal helpers ------------------------------------------------

    def _guard_supported(self) -> None:
        """Raise UnsupportedConfigError for configurations not yet supported in v0.1.0."""
        cfg = self.config
        unsupported: list[str] = []

        if cfg.order != Order.TLV:
            unsupported.append(f"order={cfg.order.value}")
        if cfg.tag_encoding != Encoding.ASCII:
            unsupported.append(f"tag_encoding={cfg.tag_encoding.value}")
        if cfg.length_encoding != Encoding.ASCII:
            unsupported.append(f"length_encoding={cfg.length_encoding.value}")
        if cfg.value_type != ValueType.ASCII:
            unsupported.append(f"value_type={cfg.value_type.value}")
        if cfg.length_includes_tag:
            unsupported.append("length_includes_tag=True")

        if unsupported:
            raise UnsupportedConfigError(
                f"Configuration not yet supported in v0.1.0: {', '.join(unsupported)}"
            )

    def _validate_tag(self, tag: str) -> None:
        cfg = self.config
        if len(tag) != cfg.tag_size:
            raise EncodingError(
                f"Tag {tag!r} has length {len(tag)}, expected {cfg.tag_size}"
            )
        self._validate_tag_alphabet(tag)

    def _validate_tag_alphabet(self, tag: str) -> None:
        """Validate that tag chars are valid for the configured tag_encoding."""
        cfg = self.config
        alphabet = self._alphabet_for(cfg.tag_encoding)
        invalid = [c for c in tag if c not in alphabet]
        if invalid:
            raise EncodingError(
                f"Tag {tag!r} contains invalid character(s) "
                f"{invalid!r} for encoding {cfg.tag_encoding.value} "
                f"(allowed: {alphabet!r})"
            )

    def _validate_value(self, value: str) -> None:
        cfg = self.config
        if not value and not cfg.allow_empty_value:
            raise EncodingError("Empty value not allowed (allow_empty_value=False)")

    def _compute_length(self, value: str) -> int:
        """Compute the length of value in the unit defined by config (ASCII: chars = bytes)."""
        return len(value)

    def _format_length(self, length: int) -> str:
        cfg = self.config
        length_str = str(length).rjust(cfg.length_size, cfg.pad_char)
        if len(length_str) > cfg.length_size:
            raise EncodingError(
                f"Length {length} exceeds maximum representable in length_size={cfg.length_size}"
            )
        return length_str

    @staticmethod
    def _read_field(encoded: str, pos: int, size: int, field_name: str) -> tuple[str, int]:
        if pos + size > len(encoded):
            raise InvalidTLVError(f"Truncated {field_name} at position {pos}")
        return encoded[pos : pos + size], pos + size

    @staticmethod
    def _alphabet_for(encoding: Encoding) -> str:
        """Return the valid character set for a given encoding.

        Used for validating that tag/value strings contain only characters that
        the encoding can faithfully represent.
        """
        if encoding == Encoding.ASCII:
            return string.ascii_letters + string.digits
        if encoding == Encoding.BCD:
            return string.digits
        if encoding == Encoding.HEX:
            return string.hexdigits
        if encoding == Encoding.BINARY:
            return string.hexdigits
        raise ValueError(f"Unknown encoding {encoding!r}")
