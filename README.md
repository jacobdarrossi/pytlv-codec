# pytlv-codec

[![CI](https://github.com/jacobdarrossi/pytlv-codec/actions/workflows/ci.yml/badge.svg)](https://github.com/jacobdarrossi/pytlv-codec/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pytlv-codec.svg)](https://pypi.org/project/pytlv-codec/)
[![Python](https://img.shields.io/pypi/pyversions/pytlv-codec.svg)](https://pypi.org/project/pytlv-codec/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Configurable TLV/LTV codec for payment protocol sub-fields (ISO 8583, acquirer-style).

## Why

Many real-world payment protocols — **ISO 8583 sub-fields** and **Latin American acquirer integrations** — use TLV/LTV encoding with configurable conventions that vary across acquirers:

- **Order:** TLV vs LTV
- **Tag/length encoding:** ASCII, BCD, HEX, binary
- **LTV variants where length includes the tag**
- **Variable-length subfields with length prefixes**

`pytlv-codec` provides a flexible, configurable codec for these formats.

## Status

🚧 Early development (v0.3.1). API may change before 1.0.

## Install

```bash
pip install pytlv-codec
```

## Quick start (simple ASCII TLV)

```python
from pytlv_codec import Codec, CodecConfig

# Default: TLV order, ASCII everywhere, 2-char tags, 4-char lengths
codec = Codec()

encoded = codec.encode({"05": "12345", "62": "teste"})
# encoded == "05000512345620005teste"

decoded = codec.decode(encoded)
# decoded == {"05": "12345", "62": "teste"}
```

## Real-world example (LTV, BCD, length includes tag)

A real Brazilian acquirer-style sub-field encoding: LTV order, BCD-encoded tag and length, length includes the tag bytes, and value is opaque binary data represented as a hex string.

```python
from pytlv_codec import Codec, CodecConfig, Encoding, Order, ValueType

config = CodecConfig(
    order=Order.LTV,
    tag_size=2,
    tag_encoding=Encoding.BCD,
    length_size=4,
    length_encoding=Encoding.BCD,
    value_type=ValueType.BINARY,
    length_includes_tag=True,
)
codec = Codec(config)

# 74 hex chars = 37 bytes of opaque binary data
opaque_payload = (
    "0544970000010009650840000001000966"
    "00000100096655534431323334350212345678"
    "06"
)

encoded = codec.encode({"33": opaque_payload})
# encoded == "0038" + "33" + opaque_payload (80 chars total = 40 bytes when packed)
# Length is 38 bytes = 1 (tag, BCD) + 37 (value, binary)

decoded = codec.decode(encoded)
# decoded == {"33": opaque_payload}
```

## Schema-driven payload (structured TLV values)

Many real-world TLV values are not opaque blobs — they are concatenations of multiple named subfields, each with its own type (BCD, ASCII, BINARY) and either fixed size or variable length with a length prefix. `SubfieldSchema` lets you describe the structure once and pack/unpack with named values.

```python
from pytlv_codec import (
    Codec, CodecConfig, Encoding, Order, ValueType,
    SubfieldSchema, Subfield, SubfieldType,
    LengthPrefix, LengthPrefixEncoding,
)

# 1. Describe the structured payload
schema = SubfieldSchema([
    Subfield("acquirer_code", SubfieldType.BCD,    size_bytes=3),   # 3 bytes BCD
    Subfield("merchant_id",   SubfieldType.BCD,    size_bytes=6),
    Subfield("currency_code", SubfieldType.ASCII,  size_bytes=3),   # "USD"
    # variable-length: length prefix is 1 byte BCD (max 99 bytes)
    Subfield(
        "merchant_name",
        SubfieldType.ASCII,
        length_prefix=LengthPrefix(LengthPrefixEncoding.BCD, size_bytes=1),
    ),
])

# 2. Pack natural values into a hex payload string
payload_hex = schema.pack({
    "acquirer_code": "054497",        # BCD digits
    "merchant_id":   "000001000965",
    "currency_code": "USD",            # ASCII text
    "merchant_name": "STORE 01",       # any length up to 99 bytes
})

# 3. Wrap in a TLV envelope (acquirer-style LTV / BCD)
codec = Codec(CodecConfig(
    order=Order.LTV,
    tag_size=2, tag_encoding=Encoding.BCD,
    length_size=4, length_encoding=Encoding.BCD,
    value_type=ValueType.BINARY,
    length_includes_tag=True,
))
encoded = codec.encode({"33": payload_hex})

# 4. Round trip: decode the envelope, then unpack the schema
decoded_envelope = codec.decode(encoded)
fields = schema.unpack(decoded_envelope["33"])
# fields == {"acquirer_code": "054497", "merchant_id": "...", "currency_code": "USD", "merchant_name": "STORE 01"}
```

## Configuration reference

```python
from pytlv_codec import CodecConfig, Encoding, Order, ValueType

CodecConfig(
    order=Order.TLV,                          # Order.TLV | Order.LTV
    tag_size=2,                               # logical units (chars/digits)
    tag_encoding=Encoding.ASCII,              # ASCII | BCD | HEX | BINARY
    length_size=4,
    length_encoding=Encoding.ASCII,
    value_type=ValueType.ASCII,               # ASCII | BCD | HEX | BINARY
    length_includes_tag=False,                # LTV: length covers tag + value
    pad_char="0",
    allow_empty_value=True,
    allow_duplicate_tags=False,
    big_endian=True,
)
```

Length is always counted as bytes-on-wire (after binary serialization downstream).

### How encodings affect bytes-on-wire

| Encoding | Bytes per logical unit |
|---|---|
| `ASCII`   | 1 char = 1 byte |
| `BCD`     | 2 digits packed in 1 byte |
| `HEX`     | 2 hex chars in 1 byte |
| `BINARY`  | 2 hex chars in 1 byte |

For BCD/HEX/BINARY, the codec works with the hex string representation of the underlying bytes. Downstream conversion to actual binary is the responsibility of the caller (or a dedicated library like `pyiso8583`).

## Custom exceptions

```python
from pytlv_codec import (
    PytlvError,           # base
    EncodingError,        # invalid input on encode
    InvalidTLVError,      # malformed stream on decode
    UnsupportedConfigError,  # config combination not implemented
)
```

All custom exceptions also inherit from `ValueError` / `NotImplementedError` so existing generic handlers continue to work.

## Development

```bash
git clone https://github.com/jacobdarrossi/pytlv-codec.git
cd pytlv-codec
pip install -e ".[dev]"
pytest
```

## License

MIT
