from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from logging import LogRecord


class RotatingFileHandlerWithSeparator(RotatingFileHandler):
    def __init__(self, filename, maxBytes=0, backupCount=0, encoding=None, errors=None):
        super().__init__(
            filename, maxBytes=maxBytes, backupCount=backupCount, encoding=encoding, delay=False, errors=errors)

        # Add separator between app launches
        self.stream.write(f'\n\n\n\n\n{120 * "="}\n\n\n\n\n\n')


class Formatter(logging.Formatter):
    PATHNAME_MAX_LEN = 20
    PATHNAME_PREFIX = '..'
    PATHNAME_ALIGN_LEN = PATHNAME_MAX_LEN + len(PATHNAME_PREFIX)

    def format(self, record: LogRecord):
        formatter = self._select_special_formatter(record)
        record.pathname = self.PATHNAME_PREFIX + record.pathname[-self.PATHNAME_MAX_LEN:]
        return formatter.format(record)

    def _select_special_formatter(self, record: LogRecord) -> logging.Formatter:
        pass


class SimpleFormatter(Formatter):
    def __init__(self):
        super().__init__()

        log_format = f'%(asctime)s | ' \
                     f'%(levelname)-8s | ' \
                     f'%(pathname){self.PATHNAME_ALIGN_LEN}s:%(lineno)-4d | ' \
                     f'%(message)s'
        self._special_formatter = logging.Formatter(log_format)

    def _select_special_formatter(self, record: LogRecord) -> logging.Formatter:
        return self._special_formatter


class ColoredFormatter(Formatter):
    # ANSI escape codes
    # See: https://www.lihaoyi.com/post/BuildyourownCommandLinewithANSIescapecodes.html
    BLACK_BOLD = '\x1b[30;1m'
    RED_BOLD = '\x1b[31;1m'
    RED_BOLD_UNDERLINE = '\x1b[31;1m\x1b[4m'
    GREEN = '\x1b[32m'
    YELLOW_BOLD = '\x1b[33;1m'
    BLUE_BOLD = '\x1b[34;1m'
    MAGENTA_BOLD = '\x1b[35;1m'
    CYAN = '\x1b[36m'
    WHITE_BOLD = '\x1b[37;1m'

    RESET = '\x1b[0m'

    COLOR_BY_LOG_LEVEL = {
        logging.DEBUG: WHITE_BOLD,
        logging.INFO: BLUE_BOLD,
        logging.WARNING: YELLOW_BOLD,
        logging.ERROR: RED_BOLD,
        logging.CRITICAL: RED_BOLD_UNDERLINE,
    }

    TIME_COLOR = GREEN
    SOURCE_COLOR = CYAN

    def __init__(self):
        super().__init__()

        self._formatter_by_log_level = {}

    def _select_special_formatter(self, record: LogRecord) -> logging.Formatter:
        return self._formatter_by_log_level.setdefault(
            record.levelno,
            self._create_formatter(record.levelno))

    def _create_formatter(self, log_level: int) -> logging.Formatter:
        level_color = self.COLOR_BY_LOG_LEVEL.get(log_level, self.MAGENTA_BOLD)
        log_format = f'{self.TIME_COLOR}%(asctime)s{self.RESET} | ' \
                     f'{level_color}%(levelname)-8s{self.RESET} | ' \
                     f'{self.SOURCE_COLOR}%(pathname){self.PATHNAME_ALIGN_LEN}s:%(lineno)-4d{self.RESET} | ' \
                     f'{level_color}%(message)s{self.RESET}'
        return logging.Formatter(log_format)
