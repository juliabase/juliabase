"""Language-independent date, time, and number formats."""

DATE_FORMAT = "Y-m-d"
SHORT_DATE_FORMAT = DATE_FORMAT
DATETIME_FORMAT = "Y-m-d H:i:s"
SHORT_DATETIME_FORMAT = "Y-m-d H:i"
TIME_FORMAT = "H:i:s"

DECIMAL_SEPARATOR = "."
THOUSAND_SEPARATOR = ","
NUMBER_GROUPING = 0

# Keep input handling consistent with the former USE_L10N=False behavior.
DATE_INPUT_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%b %d %Y",
    "%b %d, %Y",
    "%d %b %Y",
    "%d %b, %Y",
    "%B %d %Y",
    "%B %d, %Y",
    "%d %B %Y",
    "%d %B, %Y",
]
DATETIME_INPUT_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M:%S.%f",
    "%m/%d/%Y %H:%M",
    "%m/%d/%y %H:%M:%S",
    "%m/%d/%y %H:%M:%S.%f",
    "%m/%d/%y %H:%M",
]
TIME_INPUT_FORMATS = [
    "%H:%M:%S",
    "%H:%M:%S.%f",
    "%H:%M",
]
