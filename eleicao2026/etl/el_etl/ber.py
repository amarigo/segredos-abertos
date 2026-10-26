"""Minimal BER/DER parser for TSE bu.dat files."""
import sys


def parse(b, i=0, end=None):
    """Return list of (cls, constructed, tag, value_or_children)."""
    end = len(b) if end is None else end
    out = []
    while i < end:
        t = b[i]; i += 1
        cls = t >> 6; cons = bool(t & 0x20); tag = t & 0x1f
        if tag == 0x1f:
            tag = 0
            while True:
                x = b[i]; i += 1
                tag = (tag << 7) | (x & 0x7f)
                if not x & 0x80:
                    break
        L = b[i]; i += 1
        if L & 0x80:
            n = L & 0x7f
            L = int.from_bytes(b[i:i + n], 'big'); i += n
        v = b[i:i + L]
        if cons:
            out.append((cls, True, tag, parse(b, i, i + L)))
        else:
            out.append((cls, False, tag, v))
        i += L
    return out


def dump(nodes, d=0):
    for cls, cons, tag, v in nodes:
        if cons:
            print('  ' * d + f'[{cls}:{tag}] {{')
            dump(v, d + 1)
            print('  ' * d + '}')
        else:
            s = v.decode('latin-1') if all(32 <= c < 127 for c in v) and v else v.hex()[:40]
            if cls == 0 and tag in (2, 10):
                s = int.from_bytes(v, 'big', signed=True)
            print('  ' * d + f'[{cls}:{tag}] {s}')


if __name__ == '__main__':
    dump(parse(open(sys.argv[1], 'rb').read()))
