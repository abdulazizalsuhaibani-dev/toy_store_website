"""The two roles a shop has: Customer and Admin.

They are plain `django.contrib.auth` groups (there is no custom user model),
created by migration 0019. A customer holds no permissions at all: browsing,
the cart, checkout and one's own orders only need a signed-in user. An admin
holds the model permissions the staff-facing views check.
"""

CUSTOMER_GROUP = "Customer"
ADMIN_GROUP = "Admin"
