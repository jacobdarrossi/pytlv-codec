"""Configuration types for the TLV/LTV codec."""

from dataclasses import dataclass
from enum import Enum


class Order(Enum):
    """Order of components in the encoded stream."""

    TLV = "tlv"
    LTV = "ltv"


class Encoding(Enum):
    """How tag, length, or value field is represented on the wire."""

    ASCII = "ascii"
    BCD = "bcd"
    HEX = "hex"
    BINARY = "binary"


class ValueType(Enum):
    """Semantic type of the value, used for length calculation.

    Note: the codec does not transform the value bytes — it computes the
    length as if the value were going to be serialized in the given form
    downstream (e.g., by pyiso8583 or another binary codec).
    """

    ASCII = "ascii"
    BCD = "bcd"
    HEX = "hex"
    BINARY = "binary"


@dataclass
class CodecConfig:
    """Configuration for a TLV/LTV codec.

    Defaults match the simplest case: TLV order, ASCII everywhere,
    2-char tags, 4-char lengths. Length is always counted as bytes-on-wire.
    """

    order: Order = Order.TLV

    tag_size: int = 2
    tag_encoding: Encoding = Encoding.ASCII

    length_size: int = 4
    length_encoding: Encoding = Encoding.ASCII

    value_type: ValueType = ValueType.ASCII

    length_includes_tag: bool = False

    pad_char: str = "0"
    allow_empty_value: bool = True
    allow_duplicate_tags: bool = False
    big_endian: bool = True
