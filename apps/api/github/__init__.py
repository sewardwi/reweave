"""GitHub App integration: auth, webhooks, and GitWriter.

``GitWriter`` is the single module permitted to perform repository writes, and it can only
create a branch, commit to it, and open a pull request (D7). Any code path that writes to a
repository some other way is a bug, and the tests here exist to prove there isn't one.
"""
