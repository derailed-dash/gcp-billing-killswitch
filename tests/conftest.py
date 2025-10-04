"""
This module defines project-wide test fixtures for pytest.

Fixtures defined here are automatically available to all tests in the project
without needing to be imported.
"""
import pytest


@pytest.fixture(scope="session", autouse=True)
def cleanup_logging(request):
    """
    This fixture closes the Cloud Logging client at the end of the test session,
    preventing the 'CloudLoggingHandler shutting down' warning.
    """
    # Code before the yield statement is the setup phase (runs before tests).
    yield
    # Code after the yield statement is the teardown phase (runs after all tests).

    # We import here, within the teardown phase, to ensure that the application
    # module (src.main) has been fully loaded by the time we need to access it.
    from src.main import logging_client

    logging_client.close()
