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

🚧 Early development. API may change.

## Install

```bash
pip install pytlv-codec
```

## Quick start

```python
from pytlv_codec import Codec, CodecConfig

# Default: TLV, ASCII everywhere, 2-char tags, 4-char lengths
codec = Codec()

encoded = codec.encode({"05": "12345", "62": "teste"})
# encoded == "05000512345620005teste"

decoded = codec.decode(encoded)
# decoded == {"05": "12345", "62": "teste"}
```

## Configuration

```python
from pytlv_codec import Codec, CodecConfig, Order, Encoding, ValueType

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
```

See `CodecConfig` for the full list of options.

## Development

```bash
git clone https://github.com/jacobdarrossi/pytlv-codec.git
cd pytlv-codec
pip install -e ".[dev]"
pytest
```

## License

MIT
