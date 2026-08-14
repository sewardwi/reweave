#!/usr/bin/env python
"""Django management entry point."""

from __future__ import annotations

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    # Imported as a module rather than a bare name: Django's own signature is partially untyped,
    # and attribute access falls under the relaxation already scoped to apps/api in pyproject.toml
    # rather than needing an ignore comment here.
    from django.core import management

    management.execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
