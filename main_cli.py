"""
Main CLI entry point.

This module is responsible for:
1. Initializing application components via the factory
2. Creating and running the CLI application

It knows nothing about business logic, repositories, or LLM providers.
"""

import sys

from app_factory import initialize_application
from cli_app import CLIChat


def main():
    """Точка входа CLI приложения."""
    try:
        # Initialize all application components via factory
        use_cases = initialize_application()

        # Create CLI application with use cases
        cli = CLIChat(use_cases)

        # Run the CLI application
        cli.run()
    except OSError as e:
        print(f"\n[ERROR] {e}\n", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nДо свидания!\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
