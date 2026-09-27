"""FAR/LFA packing tests."""
import unittest

from layout_ecc.a7_far import (
    ECC_WORD, pack_far, pack_sem_n, unpack_far, unpack_sem_n,
)


class TestFar(unittest.TestCase):
    def test_roundtrip(self):
        far = pack_far(block=0, top=0, row=1, column=12, minor=5)
        u = unpack_far(far)
        self.assertEqual((u["row"], u["column"], u["minor"]), (1, 12, 5))

    def test_sem_n_example_shape(self):
        # C00000F640 → prefix C0, lfa 0x3D, word 50, bit 0 if that encoding
        # We only assert pack/unpack inverses, not a device-specific LFA.
        h = pack_sem_n(0xF6, ECC_WORD, 0)
        u = unpack_sem_n(h)
        self.assertEqual(u["lfa"], 0xF6)
        self.assertEqual(u["word"], ECC_WORD)
        self.assertEqual(u["bit"], 0)
        self.assertEqual(u["prefix"], 0xC0)
        self.assertEqual(unpack_sem_n("N" + h)["lfa"], 0xF6)


if __name__ == "__main__":
    unittest.main()
