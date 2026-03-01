import base64
import logging
import sys
import time
import zlib

import pandas as pd

sys.path.append(".")
from src import configs
from src import email_functions as email_func

logger = logging.getLogger(__name__)


def encode_saildocs_grib_file(file_path):
    """
    Reads the content of a GRIB file, compresses it using zlib, then encodes the compressed data into a base64 string.

    Args:
    file_path (str): Path to the GRIB file that needs to be encoded.

    Returns:
    str: Base64 encoded string representation of the zlib compressed GRIB file content.
    """

    logger.info("Encoding Saildocs GRIB file: %s", file_path)

    # Open the file in binary read mode and read its content
    with open(file_path, "rb") as file:
        grib_binary = file.read()

    # Compress the binary content using zlib
    compressed_grib = zlib.compress(grib_binary)

    # Convert the compressed content to a base64 encoded string
    encoded_data = base64.b64encode(compressed_grib).decode("utf-8")
    logger.info(
        "Finished encoding GRIB file (input bytes=%d, encoded chars=%d)",
        len(grib_binary),
        len(encoded_data),
    )

    return encoded_data


def wait_for_saildocs_response(auth_service, time_sent):
    """Wait for a SailDocs response and verify if the response matches the request timestamp.

    Args:
    auth_service: Authenticated Gmail API service instance.
    time_sent (datetime): Timestamp of the SailDocs request.

    Returns:
    dict or None: Returns the latest email response or None if no valid response is received within the timeout.
    """
    logger.info("Waiting for Saildocs response (sent at %s UTC)", time_sent.isoformat())

    for _ in range(60):  # loop for a maximum of 60 iterations (10 seconds sleep each)
        time.sleep(10)  # sleep for 10 seconds before checking for new emails
        last_response = email_func._search_gmail_messages(
            auth_service, configs.SAILDOCS_RESPONSE_EMAIL
        )[0]
        time_received = pd.to_datetime(
            auth_service.users()
            .messages()
            .get(userId="me", id=last_response["id"])
            .execute()["payload"]["headers"][-1]["value"]
            .split("(UTC)")[0]
        )
        if (
            time_received > time_sent
        ):  # compare the received timestamp with the timestamp of the SailDocs request
            logger.info("Received Saildocs response: %s", last_response["id"])
            return last_response
    logger.warning("Saildocs response wait timed out")
    return None
