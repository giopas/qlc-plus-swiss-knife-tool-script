"""3.9.0: the QR code of the tablet address (pure Python encoder, checked by decoding)."""
import pytest

from core import qr


def _decode(text):
    cv2 = pytest.importorskip('cv2')
    np = pytest.importorskip('numpy')
    m = qr.encode(text)
    n, s, q = len(m), 8, 4
    img = np.full(((n + 2 * q) * s,) * 2, 255, np.uint8)
    for y in range(n):
        for x in range(n):
            if m[y][x]:
                img[(y + q) * s:(y + q + 1) * s, (x + q) * s:(x + q + 1) * s] = 0
    return cv2.QRCodeDetector().detectAndDecode(img)[0]


@pytest.mark.parametrize('text', [
    'a', 'http://192.168.1.20:8080/', 'http://localhost:8080/?role=vocals',
    'http://192.168.100.100:8080/?role=commander&who=Guitar', 'x' * 106, 'Città è'])
def test_the_code_decodes_to_the_text(text):
    assert _decode(text) == text


def test_too_long_is_refused():
    with pytest.raises(ValueError):
        qr.encode('x' * 107)


def test_svg_is_black_on_white():
    s = qr.svg('http://10.0.0.5:8080/')
    assert s.startswith('<svg') and 'fill="#fff"' in s and 'fill="#000"' in s


def test_route(tmp_path):
    from tests.test_song_cards_390 import _client
    client, _p = _client(tmp_path, 'Festival_14fix.qxw')
    r = client.get('/api/stagemon/qr', query_string={'text': 'http://10.0.0.5:8080/?role=band'})
    assert r.status_code == 200 and r.mimetype == 'image/svg+xml'
    assert client.get('/api/stagemon/qr', query_string={'text': 'javascript:alert(1)'}).status_code == 400
    assert client.get('/api/stagemon/qr', query_string={'text': 'http://' + 'x' * 120}).status_code == 400


def test_the_screen_uses_it_without_innerhtml_for_the_image():
    js = open('static/js/stagemon.js', encoding='utf-8').read()
    body = js[js.index('function stagemonQr'):js.index('function _smServer')]
    assert 'innerHTML' not in body and "'/api/stagemon/qr?text='" in body
