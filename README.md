# pytlv-codec

Configurable TLV/LTV codec for payment protocol sub-fields (ISO 8583, acquirer-style).

## Why

Most existing TLV libraries in Python target byte-oriented BER/DER (X.690, EMV chip cards). But many real-world payment protocols — especially **ISO 8583 sub-fields** and **Latin American acquirer integrations** — use string-based TLV/LTV encoding with configurable conventions:

- **Order:** TLV vs LTV
- **Tag/length encoding:** ASCII, BCD, HEX, binary
- **Length measurement:** bytes-on-wire vs logical units
- **LTV variants where length includes the tag**

`pytlv-codec` provides a flexible, configurable codec for these formats. Built from public specs (ISO 8583, EMV Books, acquirer documentation) — no proprietary code involved.

## Status

🚧 Early development (v0.2.0). API may change before 1.0.

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

## Configuration reference

```python
from pytlv_codec import CodecConfig, Encoding, Order, ValueType, LengthMeasure

CodecConfig(
    order=Order.TLV,                          # Order.TLV | Order.LTV
    tag_size=2,                               # logical units (chars/digits)
    tag_encoding=Encoding.ASCII,              # ASCII | BCD | HEX | BINARY
    length_size=4,
    length_encoding=Encoding.ASCII,
    length_counts=LengthMeasure.BYTES_ON_WIRE,
    value_type=ValueType.ASCII,               # ASCII | BCD | HEX | BINARY
    length_includes_tag=False,                # LTV: length covers tag + value
    pad_char="0",
    allow_empty_value=True,
    allow_duplicate_tags=False,
    big_endian=True,
)
```

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
