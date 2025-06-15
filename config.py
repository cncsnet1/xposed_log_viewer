#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件
"""

import os

# 服务器配置
WEB_HOST = os.getenv('WEB_HOST', '0.0.0.0')
WEB_PORT = int(os.getenv('WEB_PORT', 5000))
UDP_HOST = os.getenv('UDP_HOST', '0.0.0.0')
UDP_PORT = int(os.getenv('UDP_PORT', 9999))

# 数据库配置
DATABASE_PATH = os.getenv('DATABASE_PATH', 'logs.db')
MAX_LOGS = int(os.getenv('MAX_LOGS', 10000))

# 日志配置
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Flask配置
SECRET_KEY = os.getenv('SECRET_KEY', 'xposed_log_viewer_secret_2024')
DEBUG = os.getenv('FLASK_ENV') == 'development'

# WebSocket配置
SOCKETIO_ASYNC_MODE = 'threading'
SOCKETIO_CORS_ALLOWED_ORIGINS = "*"

# 缓冲区配置
MAX_BUFFER_SIZE = int(os.getenv('MAX_BUFFER_SIZE', 1000))
BUFFER_FLUSH_INTERVAL = int(os.getenv('BUFFER_FLUSH_INTERVAL', 5))

# 安全配置
ALLOWED_IPS = os.getenv('ALLOWED_IPS', '').split(',') if os.getenv('ALLOWED_IPS') else []
RATE_LIMIT = os.getenv('RATE_LIMIT', '1000 per hour')

# 功能开关
ENABLE_STATISTICS = os.getenv('ENABLE_STATISTICS', 'true').lower() == 'true'
ENABLE_SEARCH = os.getenv('ENABLE_SEARCH', 'true').lower() == 'true'
ENABLE_EXPORT = os.getenv('ENABLE_EXPORT', 'true').lower() == 'true' 