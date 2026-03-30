DEV = "development"
TEST = "test"
PROD = "production"

ALL: set[str] = {DEV, TEST, PROD}
DEV_AND_TEST: set[str] = {DEV, TEST}
