from parade.pixels.rpi import encode_ws2812_spi, RESET_BYTES, _BIT0, _BIT1


def _bits(byte_val: int) -> bytes:
    return bytes(_BIT1 if byte_val & (0x80 >> i) else _BIT0 for i in range(8))


def test_frame_length_and_reset_tail():
    frame = encode_ws2812_spi([(0, 0, 0)] * 3)
    assert len(frame) == 3 * 24 + RESET_BYTES
    assert frame[-RESET_BYTES:] == bytes(RESET_BYTES)


def test_grb_order_msb_first():
    frame = encode_ws2812_spi([(0xA5, 0x01, 0x80)])
    g, r, b = frame[0:8], frame[8:16], frame[16:24]
    assert g == _bits(0x01)
    assert r == _bits(0xA5)
    assert b == _bits(0x80)


def test_brightness_scales_output():
    frame = encode_ws2812_spi([(255, 255, 255)], brightness=0.5)
    assert frame[0:8] == _bits(127)


def test_every_encoded_byte_ends_low():
    # Gaps between SPI bytes must only ever stretch a low period.
    frame = encode_ws2812_spi([(255, 170, 85)])
    assert all(b & 1 == 0 for b in frame)
