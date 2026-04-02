from django.test import SimpleTestCase
from juliabase.jb_common.utils.base import HttpResponseUnauthorized, HttpResponseSeeOther, JSONRequestException, round as jb_round

class UtilsBaseTest(SimpleTestCase):
    
    def test_http_response_unauthorized(self):
        response = HttpResponseUnauthorized()
        self.assertEqual(response.status_code, 401)

    def test_http_response_see_other(self):
        url = "/some/redirect/url/"
        response = HttpResponseSeeOther(url)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response["Location"], url)

    def test_json_request_exception(self):
        # error_number must be > 2
        with self.assertRaises(AssertionError):
            JSONRequestException(1, "Error 1")
        
        with self.assertRaises(AssertionError):
            JSONRequestException(2, "Error 2")

        exc = JSONRequestException(1001, "Test Error")
        self.assertEqual(exc.error_number, 1001)
        self.assertEqual(exc.error_message, "Test Error")
        self.assertIsInstance(exc, Exception)

    def test_round(self):
        # Using string comparison because jb_round returns a string
        self.assertEqual(jb_round(1.2345, 2), "1.2")
        self.assertEqual(jb_round(1.2345, 3), "1.23")
        # "{0:.4g}".format(1.2345) -> '1.234' usually
        self.assertEqual(jb_round(1.2345, 4), "1.234")
        
        self.assertEqual(jb_round(100, 3), "100")
        self.assertEqual(jb_round(12345, 3), "1.23e+04")
        
        # Test invalid inputs handled gracefully (implicit None return)
        self.assertIsNone(jb_round("invalid", 2))
