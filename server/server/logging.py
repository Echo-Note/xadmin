#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : logging
# author : ly_13
# date : 10/18/2024
"""自定义日志处理器与格式化器模块。"""

import logging
import os
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler

from server.utils import get_current_request


class DailyTimedRotatingFileHandler(TimedRotatingFileHandler):
    """按天轮转的日志文件处理器，保证多进程下仅一个进程完成轮转。"""

    def rotator(self, source: str, dest: str) -> None:
        """重写轮转方法，按前一天日期生成归档文件名并重命名。

        Args:
            source: 原始日志文件路径。
            dest: 目标归档文件路径（本方法会重新计算实际目标路径）。
        """
        dest = self._get_rotate_dest_filename(source)
        if os.path.exists(source) and not os.path.exists(dest):
            # 存在多个服务进程时, 保证只有一个进程成功 rotate
            os.rename(source, dest)

    @staticmethod
    def _get_rotate_dest_filename(source: str) -> str:
        """根据原始日志路径生成前一天日期命名的归档文件路径。

        Args:
            source: 原始日志文件路径。

        Returns:
            归档日志文件的完整路径。
        """
        date_yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        path = [os.path.dirname(source), date_yesterday, os.path.basename(source)]
        filename = os.path.join(*path)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        return filename


class ServerFormatter(logging.Formatter):
    """自定义日志格式化器，在日志记录中注入请求用户与请求 UUID 信息。"""

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录，附加当前请求用户与请求标识。

        Args:
            record: 日志记录对象。

        Returns:
            格式化后的日志字符串。
        """
        current_request = get_current_request()
        record.requestUser = str(current_request.user if current_request else 'SYSTEM')[:16]
        record.requestUuid = str(getattr(current_request, 'request_uuid', ""))
        return super().format(record)


class ColorHandler(logging.StreamHandler):
    """带颜色高亮的终端日志处理器，按日志级别输出不同颜色。"""

    WHITE = "0"
    RED = "31"
    GREEN = "32"
    YELLOW = "33"
    BLUE = "34"
    PURPLE = "35"

    def emit(self, record: logging.LogRecord) -> None:
        """将日志记录按级别颜色写入流。

        Args:
            record: 日志记录对象。
        """
        try:
            msg = self.format(record)
            level_color_map = {
                logging.DEBUG: self.BLUE,
                logging.INFO: self.GREEN,
                logging.WARNING: self.YELLOW,
                logging.ERROR: self.RED,
                logging.CRITICAL: self.PURPLE
            }

            csi = f"{chr(27)}["  # 控制序列引入符
            color = level_color_map.get(record.levelno, self.WHITE)

            self.stream.write(f"{csi}{color}m{msg}{csi}m\n")
            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)
