from loguru import logger as _logger


def define_log_level(print_level="INFO", logfile_level="DEBUG"):
    _logger.remove()
    # _logger.add(sys.stderr, level=print_level)
    # 李安：以下这行做了修改，原先内容是_logger.add('/config/.storage/chatiot_conversation/log.txt', level=logfile_level)
    _logger.add("log.txt", level=logfile_level)
    return _logger


_logger = define_log_level()
