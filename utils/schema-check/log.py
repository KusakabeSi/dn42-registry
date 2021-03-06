from __future__ import print_function

import os
import sys
import inspect
import datetime

OUTPUT = sys.stderr

LEVEL = ["CRIT", "ERR ", "WARN", "NOTE", "INFO", "DBUG", "...."]
CLEVEL = ["\x1B[41mCRIT\x1B[0m",
          "\x1B[31mERR \x1B[0m",
          "\x1B[33mWARN\x1B[0m",
          "\x1B[32mNOTE\x1B[0m",
          "\x1B[34mINFO\x1B[0m",
          "\x1B[90mDBUG\x1B[0m",
          "\x1B[90m....\x1B[0m"]

MSG = "{0}  {1}  {2}  {3}  {4}  {5}  ::  {6}"
CMSG = "[{1}]\x1B[90m {2}  {3}:{5} [{4}]\x1B[0m {6}\x1B[0m"
CMULTI = "[{1}]\x1B[90m {2}\x1B[0m"

VERB_CRITICAL = 0
VERB_ERROR = 1
VERB_WARN = 2
VERB_NOTICE = 3
VERB_INFO = 4
VERB_DEBUG = 5
VERB_NONE = -1


class Log:
    log_dir = ""
    log_pfx = "main"

    level_console = VERB_ERROR
    level_file = VERB_NONE
    level_full = False

    count = [0, 0, 0, 0, 0, 0]

    def __init__(self):
        self.prog_name = sys.argv[0].rsplit("/", 1)[-1]
        self.prog_name = self.prog_name.split(".", 1)[0]
        self.log_pfx = self.prog_name

    def __del__(self):
        if self.level_console >= 5:
            os.write(1, b"[\x1B[90m\x1B[90mDBUG\x1B[90m] Log Counters crit:%d err:%d warn:%d note:%d info:%d dbug:%d\x1B[0m\n" % tuple(self.count))

    def set_dir(self, name):
        if not os.path.isdir(name):
            os.makedirs(name)
        self.log_dir = name

    #  Write a message to console or log, conditionally.
    def output(self, level, message, frame=1):
        if level < 0 or level > 5:
            level = 5

        self.count[level] += 1

        # function_name = inspect.stack()[1][3]
        cur_date = datetime.datetime.now()

        (frame, file, ln, fn, lines, index) = inspect.getouterframes(
            inspect.currentframe())[frame]

        message = str(message).split("\n")
        cmsg = CMSG if self.level_full else CMULTI

        if self.level_console >= level:

            if len(message) == 1:
                if self.level_full:
                    arg = str(cur_date), CLEVEL[
                        level], self.prog_name, file, fn, ln, message[0]
                else:
                    arg = str(cur_date), CLEVEL[level], message[0]

                print(cmsg.format(*arg), file=OUTPUT)
            else:
                if self.level_full:
                    arg = str(cur_date), CLEVEL[
                        level], self.prog_name, file, fn, ln, ""
                    print(cmsg.format(*arg), file=OUTPUT)

                for line in message:
                    print(CMULTI.format(str(cur_date), CLEVEL[
                          VERB_NONE], line), file=OUTPUT)

        if self.level_file >= level:
            self.set_dir("./logs")
            log_file_name = os.path.join(
                self.log_dir, self.log_pfx + str(cur_date.strftime('%Y-%m-%d')) + ".txt")

            with open(log_file_name, "a") as logger:
                logger.write(MSG.format(str(cur_date), LEVEL[
                             level], self.prog_name, file, fn, ln, message[0]) + "\n")
                for line in message[1:]:
                    logger.write(MSG.format(str(cur_date), LEVEL[
                                 VERB_NONE], self.prog_name, file, fn, ln, line) + "\n")

    def fatal(self, message):
        self.output(VERB_CRITICAL, message, 2)
        sys.exit(1)

    def critical(self, message):
        self.output(VERB_CRITICAL, message, 2)

    def error(self, message):
        self.output(VERB_ERROR, message, 2)

    def warning(self, message):
        self.output(VERB_WARN, message, 2)

    def notice(self, message):
        self.output(VERB_NOTICE, message, 2)

    def info(self, message):
        self.output(VERB_INFO, message, 2)

    def debug(self, message):
        self.output(VERB_DEBUG, message, 2)


def fmt_exception(exc_type, exc_value, exc_traceback):
    import traceback

    lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    log_string = ''.join(line for line in lines)
    email_string = ''.join('<br />' + line for line in lines)

    return log_string, email_string


default = Log()

fatal = default.fatal
critical = default.critical
error = default.error
warning = default.warning
notice = default.notice
info = default.info
debug = default.debug


class LogException:
    stop = None

    def __init__(self, stop=True):
        self.stop = stop

    def __enter__(self, stop=True):
        pass

    def __exit__(self, exc_type, value, traceback):

        if exc_type is None:
            return True

        if exc_type is SystemExit and value.args == (0,):
            return True

        log_string, email_string = fmt_exception(exc_type, value, traceback)
        default.output(VERB_CRITICAL, 'Failure\n\n' + log_string, 2)

        if self.stop is False:
            return False

        from . import email
        email.send(default.prog_name + ' FAILURE', email_string)

        fatal("ABORTING EXECUTION")


exception = LogException
