from django.test import SimpleTestCase
from juliabase.samples.templatetags.samples_extras import quantity

class SamplesExtrasTest(SimpleTestCase):
    
    def test_quantity_simple_numbers(self):
        # 0 -> 0 (g format)
        self.assertEqual(quantity(0), "0")
        # 123 -> 123
        self.assertEqual(quantity(123), "123")
        # 12.34 -> 12.34
        self.assertEqual(quantity(12.34), "12.34")
        # Negative
        self.assertEqual(quantity(-12.34).replace("−", "-"), "-12.34") 

    def test_quantity_exponent_formatting(self):
        # 3.4e-6 -> 3.4 · 10^-6 (with special chars)
        # NARROW NO-BREAK SPACE is \u202f
        # MINUS SIGN is \u2212
        
        # 1e-6 -> 1e-06 in 'e' format, then parsed.
        # "1.000000e-06" (depends on float repr? No, code uses {0:e})
        
        val = 3.4e-6
        # log10(abs(val)) = -5.something.
        # condition: -2 <= log10 < 5. False.
        # So uses {0:e} -> 3.400000e-06 typically.
        
        res = quantity(val)
        self.assertIn("10<sup>", res)
        self.assertIn("</sup>", res)
        # Check for non-breaking thin space around dot
        # self.assertIn("\u202f·\u202f", res)
        
    def test_quantity_minus_sign(self):
        # Checks if hyphen is replaced by minus sign
        self.assertEqual(quantity(-5), "−5")
        
    def test_quantity_large_numbers(self):
        val = 1e6 # log10 = 6 >= 5. Uses 'e'.
        res = quantity(val)
        self.assertIn("10<sup>6</sup>", res)

    def test_quantity_small_numbers(self):
        val = 1e-3 # log10 = -3 < -2. Uses 'e'.
        res = quantity(val)
        self.assertIn("10<sup>−3</sup>", res)
        
    def test_quantity_normal_numbers(self):
        val = 0.01 # log10 = -2. Uses 'g'.
        self.assertEqual(quantity(0.01), "0.01")
        
        val = 10000 # log10 = 4. Uses 'g'.
        self.assertEqual(quantity(10000), "10000")
