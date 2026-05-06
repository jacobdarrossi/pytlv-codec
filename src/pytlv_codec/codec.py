"""Codec for encoding and decoding TLV/LTV streams.

The codec is string-in / string-out. For non-ASCII encodings (BCD, HEX, BINARY),
the strings represent the hex representation of the underlying bytes — downstream
conversion to actual binary is the responsibility of the caller (or a downstream
library like pyiso8583).

Supported features:
- Order.TLV and Order.LTV
- length_includes_tag flag (LTV variants where length covers tag + value)
- All encodings (ASCII, BCD, HEX, BINARY) for tag and length
- All value types (ASCII, BCD, HEX, BINARY) for length calculation

Length is always counted in bytes-on-wire (after binary serialization downstream).
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
)


class Codec:
    """Encode and decode dict ↔ TLV/LTV string."""

    def __init__(self, config: CodecConfig | None = None) -> None:
        self.config = config or CodecConfig()

    # -- Public API ------------------------------------------------------

    def encode(self, data: dict[str, str]) -> str:
        """Encode a dict of {tag: value} pairs into a TLV/LTV string."""
        cfg = self.config
        parts: list[str] = []

        for tag, value in data.items():
            self._validate_tag(tag)
            self._validate_value(value)

            length = self._compute_length(value)
            length_str = self._format_length(length)

            if cfg.order == Order.TLV:
                parts.append(tag + length_str + value)
            else:  # LTV
                parts.append(length_str + tag + value)

        return "".join(parts)

    def decode(self, encoded: str) -> dict[str, str]:
        """Decode a TLV/LTV string back into a dict of {tag: value} pairs."""
        cfg = self.config
        result: dict[str, str] = {}
        pos = 0

        while pos < len(encoded):
            if cfg.order == Order.TLV:
                tag, pos = self._read_field(encoded, pos, cfg.tag_size, "tag")
                self._validate_tag_alphabet(tag)
                length_str, pos = self._read_field(encoded, pos, cfg.length_size, "length")
                length = self._parse_length(length_str, pos - cfg.length_size)
                value_chars = self._value_chars_for_length(length)
            else:  # LTV
                length_str, pos = self._read_field(encoded, pos, cfg.length_size, "length")
                length = self._parse_length(length_str, pos - cfg.length_size)
                tag, pos = self._read_field(encoded, pos, cfg.tag_size, "tag")
                self._validate_tag_alphabet(tag)

                if cfg.length_includes_tag:
                    tag_bytes = self._field_wire_bytes(cfg.tag_size, cfg.tag_encoding)
                    value_bytes = length - tag_bytes
                    if value_bytes < 0:
                        raise InvalidTLVError(
                            f"Length {length} smaller than tag size {tag_bytes} bytes "
                            f"(length_includes_tag=True)"
                        )
                    value_chars = self._wire_bytes_to_value_chars(value_bytes)
                else:
                    value_chars = self._value_chars_for_length(length)

            value, pos = self._read_field(encoded, pos, value_chars, "value")

            if tag in result and not cfg.allow_duplicate_tags:
                raise InvalidTLVError(f"Duplicate tag {tag!r} not allowed")

            result[tag] = value

        return result

    # -- Internal helpers ------------------------------------------------

    def _validate_tag(self, tag: str) -> None:
        cfg = self.config
        if len(tag) != cfg.tag_size:
            raise EncodingError(f"Tag {tag!r} has length {len(tag)}, expected {cfg.tag_size}")
        self._validate_tag_alphabet(tag)

    def _validate_tag_alphabet(self, tag: str) -> None:
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

        # Validate value alphabet against value_type's expected encoding
        # (ASCII allows any text; non-ASCII types require hex chars)
        if cfg.value_type != ValueType.ASCII:
            alphabet = self._alphabet_for_value_type(cfg.value_type)
            invalid = [c for c in value if c not in alphabet]
            if invalid:
                raise EncodingError(
                    f"Value {value!r} contains invalid character(s) "
                    f"{invalid!r} for value_type {cfg.value_type.value} "
                    f"(allowed: {alphabet!r})"
                )

            # BCD/HEX/BINARY: hex repr must have even length to map cleanly to bytes
            if len(value) % 2 != 0:
                raise EncodingError(
                    f"Value {value!r} (value_type={cfg.value_type.value}) "
                    f"must have an even number of characters"
                )

    def _compute_length(self, value: str) -> int:
        """Compute the length value to put in the length field, in bytes-on-wire."""
        cfg = self.config

        value_bytes = self._value_wire_bytes(value)

        if cfg.length_includes_tag:
            tag_bytes = self._field_wire_bytes(cfg.tag_size, cfg.tag_encoding)
            return value_bytes + tag_bytes

        return value_bytes

    def _value_wire_bytes(self, value: str) -> int:
        """How many bytes the value occupies on the wire."""
        cfg = self.config
        if cfg.value_type == ValueType.ASCII:
            return len(value)
        # BCD/HEX/BINARY: 2 hex chars = 1 byte
        return len(value) // 2

    def _format_length(self, length: int) -> str:
        cfg = self.config
        length_str = str(length).rjust(cfg.length_size, cfg.pad_char)
        if len(length_str) > cfg.length_size:
            raise EncodingError(
                f"Length {length} exceeds maximum representable in length_size={cfg.length_size}"
            )
        return length_str

    def _parse_length(self, length_str: str, position: int) -> int:
        try:
            return int(length_str)
        except ValueError as exc:
            raise InvalidTLVError(f"Invalid length {length_str!r} at position {position}") from exc

    def _value_chars_for_length(self, length_in_bytes: int) -> int:
        """How many string chars correspond to length_in_bytes for the configured value_type."""
        cfg = self.config
        if cfg.value_type == ValueType.ASCII:
            return length_in_bytes
        # BCD/HEX/BINARY: 1 byte = 2 hex chars
        return length_in_bytes * 2

    def _wire_bytes_to_value_chars(self, value_bytes: int) -> int:
        """Same as _value_chars_for_length, named for clarity in LTV path."""
        return self._value_chars_for_length(value_bytes)

    @staticmethod
    def _read_field(encoded: str, pos: int, size: int, field_name: str) -> tuple[str, int]:
        if pos + size > len(encoded):
            raise InvalidTLVError(f"Truncated {field_name} at position {pos}")
        return encoded[pos : pos + size], pos + size

    @staticmethod
    def _field_wire_bytes(size_in_units: int, encoding: Encoding) -> int:
        """How many wire bytes for a tag/length field of given size_in_units."""
        if encoding == Encoding.ASCII:
            return size_in_units
        # BCD/HEX/BINARY: 2 chars = 1 byte
        return size_in_units // 2

    @staticmethod
    def _alphabet_for(encoding: Encoding) -> str:
        """Valid character set for tag/length encoding."""
        if encoding == Encoding.ASCII:
            return string.ascii_letters + string.digits
        if encoding == Encoding.BCD:
            return string.digits
        if encoding == Encoding.HEX:
            return string.hexdigits
        if encoding == Encoding.BINARY:
            return string.hexdigits
        raise ValueError(f"Unknown encoding {encoding!r}")

    @staticmethod
    def _alphabet_for_value_type(value_type: ValueType) -> str:
        """Valid character set for value_type."""
        if value_type == ValueType.ASCII:
            # ASCII values can contain any printable text — no restriction at this layer
            return string.printable
        if value_type == ValueType.BCD:
            return string.digits
        if value_type == ValueType.HEX:
            return string.hexdigits
        if value_type == ValueType.BINARY:
            return string.hexdigits
        raise ValueError(f"Unknown value_type {value_type!r}")
