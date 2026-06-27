from django.test import SimpleTestCase
from unittest.mock import patch
import re
from juliabase.samples.utils.sample_name_formats import sample_name_format, verbose_sample_name_format, get_renamable_name_formats

class SampleNameFormatsTest(SimpleTestCase):
    
    def test_sample_name_format(self):
        mock_formats = {
            "format1": {
                "regex": re.compile(r"TEST-\d+"),
                "verbose_name": "Test Format 1"
            },
            "format2": {
                "regex": re.compile(r"ABC\d+"),
                "verbose_name": "Format 2"
            }
        }
        
        with patch("django.conf.settings.SAMPLE_NAME_FORMATS", mock_formats):
            # Test match
            self.assertEqual(sample_name_format("TEST-123"), "format1")
            self.assertEqual(sample_name_format("ABC99"), "format2")
            
            # Test no match
            self.assertIsNone(sample_name_format("INVALID"))
            
            # Test with match object
            fmt, match = sample_name_format("TEST-123", with_match_object=True)
            self.assertEqual(fmt, "format1")
            self.assertTrue(match)
            self.assertEqual(match.group(0), "TEST-123")
            
            # Test no match with match object
            fmt, match = sample_name_format("INVALID", with_match_object=True)
            self.assertIsNone(fmt)
            self.assertIsNone(match)

    def test_verbose_sample_name_format(self):
        mock_formats = {
            "format1": {
                "verbose_name": "Test Format 1"
            }
        }
        with patch("django.conf.settings.SAMPLE_NAME_FORMATS", mock_formats):
             self.assertEqual(verbose_sample_name_format("format1"), "Test Format 1")

    def test_get_renamable_name_formats(self):
        mock_formats = {
            "renamable": {"possible_renames": True, "regex": re.compile(r"A")},
            "fixed": {"possible_renames": None, "regex": re.compile(r"B")},
            "also_renamable": {"possible_renames": ["foo"], "regex": re.compile(r"C")}
        }
        
        # We need to reset the global variable cache in the module, if any
        # But looking at implementation:
        # renamable_name_formats = None
        # def get_renamable_name_formats(): ...
        
        # We need to manually reset the cache
        import juliabase.samples.utils.sample_name_formats as module
        module.renamable_name_formats = None
        
        with patch("django.conf.settings.SAMPLE_NAME_FORMATS", mock_formats):
            renamable = get_renamable_name_formats()
            self.assertIn("renamable", renamable)
            self.assertIn("also_renamable", renamable)
            self.assertNotIn("fixed", renamable)
