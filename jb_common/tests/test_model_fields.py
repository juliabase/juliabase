from django.test import SimpleTestCase
from juliabase.jb_common import model_fields

class ModelFieldsTest(SimpleTestCase):
    
    def test_decimal_quantity_field(self):
        field = model_fields.DecimalQuantityField(max_digits=10, decimal_places=2, unit="mbar")
        self.assertEqual(field.unit, "mbar")
        self.assertEqual(field.description, "Fixed-point number in the unit of %(unit)s")
        
        form_field = field.formfield()
        self.assertEqual(form_field.unit, "mbar")

    def test_float_quantity_field(self):
        field = model_fields.FloatQuantityField(unit="kg")
        self.assertEqual(field.unit, "kg")
        form_field = field.formfield()
        self.assertEqual(form_field.unit, "kg")

    def test_integer_quantity_field(self):
        field = model_fields.IntegerQuantityField(unit="count")
        self.assertEqual(field.unit, "count")
        form_field = field.formfield()
        self.assertEqual(form_field.unit, "count")

    def test_positive_integer_quantity_field(self):
        field = model_fields.PositiveIntegerQuantityField(unit="s")
        self.assertEqual(field.unit, "s")
        form_field = field.formfield()
        self.assertEqual(form_field.unit, "s")
    
    def test_small_integer_quantity_field(self):
        field = model_fields.SmallIntegerQuantityField(unit="V")
        self.assertEqual(field.unit, "V")
        form_field = field.formfield()
        self.assertEqual(form_field.unit, "V")

    def test_positive_small_integer_quantity_field(self):
        field = model_fields.PositiveSmallIntegerQuantityField(unit="A")
        self.assertEqual(field.unit, "A")
        form_field = field.formfield()
        self.assertEqual(form_field.unit, "A")
