#
# Use this sctipt to generate autoincremented values
#
# s = """
#     E_NO_ERROR = 1
#     E_INTERNAL_ERROR = 2
#     E_POOL_NOT_FOUND = 3
#     E_POOL_LIMIT_EXCEEDED = 4
# """
#
# s = s.strip()
# for i, line in enumerate(s.splitlines()):
#     key, _ = line.strip().replace(" ", "").split("=")
#     print(f"{key} = {i}")
#

E_NO_ERROR = 0
E_INTERNAL_ERROR = 1
E_POOL_NOT_FOUND = 2
E_POOL_TOO_SMALL = 3
E_POOL_NO_RESOURCES = 4
E_POOL_LOCKED = 5
