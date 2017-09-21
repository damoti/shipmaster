import logging
from shipmaster.core.plugins import Plugin

logger = logging.getLogger('shipmaster.builder')


class LogPlugin(Plugin):

    def handle_log_output(self, b, line):
        logger.info(line)

    def before_build(self, b):
        logger.info('BUILDING {} FROM {}'.format(b.config.name, b.config.from_image))

    def before_archive_upload(self, b):
        logger.info('Uploading...')

    def before_container_start(self, b):
        logger.info('Starting...')
