import argparse
import logging
import sys
import time

import coloredlogs

sys.path.append(".")
from src import email_functions as email_func
from src import inreach_functions as inreach_func
from src import saildoc_functions as saildoc_func

logger = logging.getLogger(__name__)


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Marine GRIB inReach transmitter service"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase logging verbosity (use -v for INFO, -vv for DEBUG)",
    )
    return parser.parse_args(argv)


def configure_logging(verbosity):
    level = logging.INFO
    if verbosity >= 2:
        level = logging.DEBUG

    coloredlogs.install(
        level=level,
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    configure_logging(args.verbose)

    # authenticate Gmail API
    auth_service = email_func.gmail_authenticate()

    # check for new InReach messages every minute
    while True:
        logger.info("Checking for new inReach messages")

        # check for new messages and retrieve GRIB path and Garmin reply URL
        result = email_func.process_new_inreach_message(auth_service)

        # if a new message is received
        if result is not None:
            logger.debug("email_func result: %s", result)
            grib_path, garmin_reply_url = result

            # encode GRIB to binary
            encoded_grib = saildoc_func.encode_saildocs_grib_file(grib_path)

            # send the encoded GRIB to InReach
            inreach_func.send_messages_to_inreach(garmin_reply_url, encoded_grib)

        # wait for the next check in 60 seconds
        time.sleep(60)
