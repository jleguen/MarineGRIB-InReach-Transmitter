import logging
import random
import re
import sys
import time
from urllib.parse import parse_qs, urlparse

import requests

sys.path.append(".")
from src import configs

logger = logging.getLogger(__name__)


def send_messages_to_inreach(url, gribmessage):
    """
    Splits the gribmessage and sends each part to InReach.

    Parameters:
    - url (str): The target URL for the InReach API.
    - gribmessage (str): The full message string to be split and sent.

    Returns:
    - list: A list of response objects from the InReach API for each sent message.
    """
    message_parts = _split_message(gribmessage)
    logger.info("GRIB msg %d bytes, %d parts", len(gribmessage), len(message_parts))
    logger.info("Sending to %s", url)
    send_context = _build_send_context(url)

    responses = []
    for part in message_parts:
        responses.append(_post_request_to_inreach(url, part, send_context))
        # Introducing a delay to prevent overwhelming the API
        time.sleep(configs.DELAY_BETWEEN_MESSAGES)

    return responses


######## HELPERS ########


def _split_message(gribmessage):
    """
    Splits a given grib message into chunks and encapsulates each chunk with its index.

    Args:
    gribmessage (str): The grib message that needs to be split into chunks.

    Returns:
    list: A list of formatted strings where each string has the format `msg {index}/{total_splits}:\n{chunk}\nend`.
    """
    total_splits = (
        len(gribmessage) + configs.MESSAGE_SPLIT_LENGTH - 1
    ) // configs.MESSAGE_SPLIT_LENGTH

    chunks = [
        gribmessage[i : i + configs.MESSAGE_SPLIT_LENGTH]
        for i in range(0, len(gribmessage), configs.MESSAGE_SPLIT_LENGTH)
    ]

    formatted_chunks = [
        f"msg {index + 1}/{total_splits}:\n{chunk}\nend"
        for index, chunk in enumerate(chunks)
    ]
    return formatted_chunks


def _post_request_to_inreach(url, message_str, send_context=None):
    """
    Sends a post request with the message to the specified InReach URL.

    Args:
    url (str): The InReach endpoint URL to send the post request.
    message_str (str): The message string to be sent to InReach.

    Returns:
    Response: A Response object containing the server's response to the request.
    """
    context = send_context or _build_send_context(url)
    if context["mode"] == "page-json":
        payload = {
            "ReplyAddress": configs.GMAIL_ADDRESS,
            "ReplyMessage": message_str,
            "Guid": context["guid"],
            "MessageId": str(random.randint(10000000, 99999999)),
            # "MessageId": context["message_id"],
        }
        headers = {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }
        logger.debug("Sending page-json payload: %s", payload)
        response = context["session"].post(
            context["post_url"],
            json=payload,
            headers=headers,
            timeout=30,
        )
    else:
        # Fallback to legacy flow using extId from the URL.
        guid = context["guid"]
        data = {
            "ReplyAddress": configs.GMAIL_ADDRESS,
            "ReplyMessage": message_str,
            "MessageId": str(random.randint(10000000, 99999999)),
            "Guid": guid,
        }
        logger.debug("Sending legacy form payload: %s", data)
        response = requests.post(
            url,
            cookies=configs.INREACH_COOKIES,
            headers=configs.INREACH_HEADERS,
            data=data,
        )

    if response.status_code == 200:
        logger.info("Reply to InReach sent successfully")
        logger.debug("Sent inReach message chunk: %s", message_str)
    else:
        logger.error("Error sending inReach message chunk")
        logger.error("Status code: %s", response.status_code)
        logger.error("Response content: %s", response.content)
        logger.debug("Failed chunk content: %s", message_str)

    return response


def _build_send_context(url):
    """Build send context from inReach page by resolving redirect and hidden fields.

    Returns a context dict for either the modern JSON flow or legacy fallback flow.
    """
    session = requests.Session()
    try:
        resp = session.get(url, allow_redirects=True, timeout=30)
        resp.raise_for_status()
        final_url = resp.url
        guid = _extract_hidden_field(resp.text, "Guid")
        message_id = _extract_hidden_field(resp.text, "MessageId")

        if guid and message_id:
            parsed = urlparse(final_url)
            post_url = f"{parsed.scheme}://{parsed.netloc}/TextMessage/TxtMsg"
            logger.info("Using page-json flow via %s", post_url)
            return {
                "mode": "page-json",
                "session": session,
                "post_url": post_url,
                "guid": guid,
                "message_id": message_id,
            }
    except requests.RequestException as exc:
        logger.warning("Could not initialize page-json send context: %s", exc)

    legacy_guid = _extract_ext_id(url)
    logger.warning("Falling back to legacy send flow")
    return {"mode": "legacy", "guid": legacy_guid}


def _extract_hidden_field(html, field_id):
    pattern = rf'id="{re.escape(field_id)}"[^>]*value="([^"]+)"'
    match = re.search(pattern, html, flags=re.IGNORECASE)
    return match.group(1) if match else None


def _extract_ext_id(url):
    parsed = urlparse(url)
    ext_id = parse_qs(parsed.query).get("extId", [None])[0]
    if not ext_id:
        raise ValueError(f"Could not extract extId from URL: {url}")
    return ext_id
