"""Schema-driven payload pack/unpack for structured TLV values.

Many real-world TLV values are not opaque blobs — they are concatenations of
multiple named subfields, each with its own type (BCD, ASCII, BINARY) and
either a fixed size or a length prefix.

This module provides a Schema abstraction so callers can describe the structure
once and pack/unpack named values without manually concatenating bytes.

The pack output is the hex-string representation of the concatenated bytes,
suitable for use as the value of a TLV with `value_type=ValueType.BINARY`.
"""

from __future__ import annotations

import string
from dataclasses import dataclass
from enum import Enum

from pytlv_codec.exceptions import EncodingError, InvalidTLVError


class SubfieldType(Enum):
    """Semantic type of a subfield's natural representation."""

    BCD = "bcd"      # value is a string of decimal digits (0-9)
    ASCII = "ascii"  # value is ASCII text
    BINARY = "binary"  # value is a hex string


class LengthPrefixEncoding(Enum):
    """How a variable-length subfield's length prefix is encoded on the wire."""

    BCD = "bcd"
    ASCII = "ascii"
    BINARY = "binary"


@dataclass(frozen=True)
class LengthPrefix:
    """Configuration for a variable-length subfield's length prefix."""

    encoding: LengthPrefixEncoding
    size_bytes: int  # bytes the prefix occupies on the wire

    def __post_init__(self) -> None:
        if self.size_bytes <= 0:
            raise ValueError(
                f"LengthPrefix.size_bytes must be > 0, got {self.size_bytes}"
            )

    @property
    def hex_chars(self) -> int:
        """How many hex chars the prefix occupies in the schema's hex output."""
        return self.size_bytes * 2

    @property
    def max_value(self) -> int:
        """Maximum length (in bytes) representable by this prefix."""
        if self.encoding == LengthPrefixEncoding.BCD:
            return 10 ** (self.size_bytes * 2) - 1
        if self.encoding == LengthPrefixEncoding.ASCII:
            return 10 ** self.size_bytes - 1
        if self.encoding == LengthPrefixEncoding.BINARY:
            return 256 ** self.size_bytes - 1
        raise ValueError(f"Unknown LengthPrefixEncoding {self.encoding!r}")


@dataclass(frozen=True)
class Subfield:
    """A subfield definition.

    Either ``size_bytes`` (fixed-size) or ``length_prefix`` (variable-size)
    must be set, but not both.
    """

    name: str
    type: SubfieldType
    size_bytes: int = 0
    length_prefix: LengthPrefix | None = None

    def __post_init__(self) -> None:
        if self.length_prefix is None and self.size_bytes <= 0:
            raise ValueError(
                f"Subfield {self.name!r}: must specify size_bytes (fixed) "
                f"or length_prefix (variable)"
            )
        if self.length_prefix is not None and self.size_bytes > 0:
            raise ValueError(
                f"Subfield {self.name!r}: cannot specify both size_bytes and length_prefix"
            )

    @property
    def is_variable(self) -> bool:
        return self.length_prefix is not None


class SubfieldSchema:
    """A schema describing a sequence of concatenated subfields.

    Use ``pack()`` to convert a dict of named values into a hex-string
    representation suitable for the value of a TLV with
    ``value_type=ValueType.BINARY``. Use ``unpack()`` for the reverse.
    """

    def __init__(self, subfields: list[Subfield]) -> None:
        if not subfields:
            raise ValueError("Schema must have at least one subfield")

        names = [sf.name for sf in subfields]
        if len(names) != len(set(names)):
            duplicates = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(f"Duplicate subfield names: {duplicates}")

        self.subfields = list(subfields)

    # -- Public API ------------------------------------------------------

    def pack(self, data: dict[str, str]) -> str:
        """Pack named values into a concatenated hex-string representation."""
        missing = [sf.name for sf in self.subfields if sf.name not in data]
        if missing:
            raise EncodingError(f"Missing subfield(s): {missing}")

        known = {sf.name for sf in self.subfields}
        unknown = sorted(k for k in data if k not in known)
        if unknown:
            raise EncodingError(f"Unknown subfield(s) not in schema: {unknown}")

        parts: list[str] = []
        for sf in self.subfields:
            value = data[sf.name]
            if sf.is_variable:
                hex_value = self._encode_value_variable(value, sf)
                value_bytes = len(hex_value) // 2
                assert sf.length_prefix is not None  # narrowed by is_variable
                if value_bytes > sf.length_prefix.max_value:
                    raise EncodingError(
                        f"Subfield {sf.name!r}: value of {value_bytes} bytes "
                        f"exceeds max {sf.length_prefix.max_value} for prefix "
                        f"({sf.length_prefix.encoding.value}, "
                        f"{sf.length_prefix.size_bytes} bytes)"
                    )
                hex_prefix = self._encode_length_prefix(value_bytes, sf.length_prefix)
                parts.append(hex_prefix + hex_value)
            else:
                parts.append(self._encode_value_fixed(value, sf))

        return "".join(parts)

    def unpack(self, hex_str: str) -> dict[str, str]:
        """Parse a hex-string into the named subfield values."""
        result: dict[str, str] = {}
        pos = 0

        for sf in self.subfields:
            if sf.is_variable:
                assert sf.length_prefix is not None
                prefix_chars = sf.length_prefix.hex_chars
                if pos + prefix_chars > len(hex_str):
                    raise InvalidTLVError(
                        f"Truncated length prefix for subfield {sf.name!r} at position {pos}"
                    )
                prefix_chunk = hex_str[pos : pos + prefix_chars]
                value_bytes = self._decode_length_prefix(prefix_chunk, sf.length_prefix)
                pos += prefix_chars

                value_chars = value_bytes * 2
                if pos + value_chars > len(hex_str):
                    raise InvalidTLVError(
                        f"Truncated value for subfield {sf.name!r} at position {pos}"
                    )
                chunk = hex_str[pos : pos + value_chars]
                result[sf.name] = self._decode_value(chunk, sf.type)
                pos += value_chars
            else:
                chars = sf.size_bytes * 2
                if pos + chars > len(hex_str):
                    raise InvalidTLVError(
                        f"Truncated subfield {sf.name!r} at position {pos}"
                    )
                chunk = hex_str[pos : pos + chars]
                result[sf.name] = self._decode_value(chunk, sf.type)
                pos += chars

        if pos != len(hex_str):
            raise InvalidTLVError(
                f"Extra data after schema: {len(hex_str) - pos} unconsumed chars"
            )

        return result

    # -- Internal helpers ------------------------------------------------

    @staticmethod
    def _encode_value_fixed(value: str, sf: Subfield) -> str:
        if sf.type == SubfieldType.BCD:
            expected = sf.size_bytes * 2
            if len(value) != expected:
                raise EncodingError(
                    f"Subfield {sf.name!r}: BCD expects {expected} digits, got {len(value)}"
                )
            if not all(c in string.digits for c in value):
                raise EncodingError(
                    f"Subfield {sf.name!r}: BCD value contains non-digit char(s) — got {value!r}"
                )
            return value.upper()

        if sf.type == SubfieldType.ASCII:
            if len(value) != sf.size_bytes:
                raise EncodingError(
                    f"Subfield {sf.name!r}: ASCII expects {sf.size_bytes} chars, got {len(value)}"
                )
            try:
                return value.encode("ascii").hex().upper()
            except UnicodeEncodeError as exc:
                raise EncodingError(
                    f"Subfield {sf.name!r}: value contains non-ASCII characters"
                ) from exc

        if sf.type == SubfieldType.BINARY:
            expected = sf.size_bytes * 2
            if len(value) != expected:
                raise EncodingError(
                    f"Subfield {sf.name!r}: BINARY expects {expected} hex chars, got {len(value)}"
                )
            if not all(c in string.hexdigits for c in value):
                raise EncodingError(
                    f"Subfield {sf.name!r}: BINARY value contains non-hex char(s) — got {value!r}"
                )
            return value.upper()

        raise ValueError(f"Unknown SubfieldType {sf.type!r}")

    @staticmethod
    def _encode_value_variable(value: str, sf: Subfield) -> str:
        if sf.type == SubfieldType.BCD:
            if not all(c in string.digits for c in value):
                raise EncodingError(
                    f"Subfield {sf.name!r}: BCD value contains non-digit char(s)"
                )
            if len(value) % 2 != 0:
                raise EncodingError(
                    f"Subfield {sf.name!r}: variable BCD value must have even number of digits"
                )
            return value.upper()

        if sf.type == SubfieldType.ASCII:
            try:
                return value.encode("ascii").hex().upper()
            except UnicodeEncodeError as exc:
                raise EncodingError(
                    f"Subfield {sf.name!r}: value contains non-ASCII characters"
                ) from exc

        if sf.type == SubfieldType.BINARY:
            if not all(c in string.hexdigits for c in value):
                raise EncodingError(
                    f"Subfield {sf.name!r}: BINARY value contains non-hex char(s)"
                )
            if len(value) % 2 != 0:
                raise EncodingError(
                    f"Subfield {sf.name!r}: variable BINARY value must have even number of hex chars"
                )
            return value.upper()

        raise ValueError(f"Unknown SubfieldType {sf.type!r}")

    @staticmethod
    def _decode_value(hex_chunk: str, type_: SubfieldType) -> str:
        if type_ == SubfieldType.BCD:
            return hex_chunk
        if type_ == SubfieldType.ASCII:
            try:
                return bytes.fromhex(hex_chunk).decode("ascii")
            except (UnicodeDecodeError, ValueError) as exc:
                raise InvalidTLVError(
                    f"ASCII subfield contains invalid bytes for hex chunk {hex_chunk!r}"
                ) from exc
        if type_ == SubfieldType.BINARY:
            return hex_chunk.upper()
        raise ValueError(f"Unknown SubfieldType {type_!r}")

    @staticmethod
    def _encode_length_prefix(value_bytes: int, prefix: LengthPrefix) -> str:
        if prefix.encoding == LengthPrefixEncoding.BCD:
            digits = prefix.size_bytes * 2
            return f"{value_bytes:0{digits}d}"
        if prefix.encoding == LengthPrefixEncoding.ASCII:
            chars = prefix.size_bytes
            ascii_str = f"{value_bytes:0{chars}d}"
            return ascii_str.encode("ascii").hex().upper()
        if prefix.encoding == LengthPrefixEncoding.BINARY:
            return value_bytes.to_bytes(prefix.size_bytes, "big").hex().upper()
        raise ValueError(f"Unknown LengthPrefixEncoding {prefix.encoding!r}")

    @staticmethod
    def _decode_length_prefix(hex_chunk: str, prefix: LengthPrefix) -> int:
        if prefix.encoding == LengthPrefixEncoding.BCD:
            try:
                return int(hex_chunk)
            except ValueError as exc:
                raise InvalidTLVError(
                    f"Invalid BCD length prefix {hex_chunk!r}"
                ) from exc
        if prefix.encoding == LengthPrefixEncoding.ASCII:
            try:
                ascii_str = bytes.fromhex(hex_chunk).decode("ascii")
                return int(ascii_str)
            except (ValueError, UnicodeDecodeError) as exc:
                raise InvalidTLVError(
                    f"Invalid ASCII length prefix {hex_chunk!r}"
                ) from exc
        if prefix.encoding == LengthPrefixEncoding.BINARY:
            try:
                return int.from_bytes(bytes.fromhex(hex_chunk), "big")
            except ValueError as exc:
                raise InvalidTLVError(
                    f"Invalid binary length prefix {hex_chunk!r}"
                ) from exc
        raise ValueError(f"Unknown LengthPrefixEncoding {prefix.encoding!r}")
