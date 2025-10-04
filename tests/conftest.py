import pytest


@pytest.fixture(scope="session", autouse=True)
def cleanup_logging(request):
    """
    This fixture closes the Cloud Logging client at the end of the test session,
    preventing the 'CloudLoggingHandler shutting down' warning.
    """
    yield

    # Import the client from the application module
    from src.main import logging_client

    logging_client.close()
