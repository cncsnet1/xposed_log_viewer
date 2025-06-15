#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Xposed日志查看器 - 主Web应用
功能：接收UDP日志并通过Web界面展示
作者：AI助手
版本：1.0
"""

import json
import sqlite3
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import logging
import os

# 创建Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'xposed_log_viewer_secret_2024'

# 初始化WebSocket
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全局变量
log_buffer = []  # 内存中的日志缓冲区
max_buffer_size = 1000  # 最大缓冲区大小
clients_count = 0  # 连接的客户端数量

class LogDatabase:
    """日志数据库管理类"""
    
    def __init__(self, db_path='logs.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                tag TEXT,
                message TEXT NOT NULL,
                source_ip TEXT,
                app_package TEXT,
                hook_point TEXT,
                data_type TEXT,
                raw_data TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建索引提高查询性能
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON logs(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_level ON logs(level)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tag ON logs(tag)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_app_package ON logs(app_package)')
        
        conn.commit()
        conn.close()
        logger.info("数据库初始化完成")
    
    def insert_log(self, log_data):
        """插入日志记录"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO logs (timestamp, level, tag, message, source_ip, 
                                app_package, hook_point, data_type, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                log_data.get('timestamp', ''),
                log_data.get('level', 'INFO'),
                log_data.get('tag', ''),
                log_data.get('message', ''),
                log_data.get('source_ip', ''),
                log_data.get('app_package', ''),
                log_data.get('hook_point', ''),
                log_data.get('data_type', ''),
                log_data.get('raw_data', '')
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"插入日志失败: {e}")
            return False
    
    def get_logs(self, limit=100, offset=0, level_filter=None, search_text=None):
        """获取日志记录"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 构建查询条件
            where_conditions = []
            params = []
            
            if level_filter and level_filter != 'ALL':
                where_conditions.append('level = ?')
                params.append(level_filter)
            
            if search_text:
                where_conditions.append('(message LIKE ? OR tag LIKE ? OR app_package LIKE ?)')
                search_pattern = f'%{search_text}%'
                params.extend([search_pattern, search_pattern, search_pattern])
            
            where_clause = ' WHERE ' + ' AND '.join(where_conditions) if where_conditions else ''
            
            query = f'''
                SELECT id, timestamp, level, tag, message, source_ip, 
                       app_package, hook_point, data_type, raw_data, created_at
                FROM logs 
                {where_clause}
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            '''
            
            params.extend([limit, offset])
            cursor.execute(query, params)
            
            columns = [description[0] for description in cursor.description]
            logs = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            conn.close()
            return logs
        except Exception as e:
            logger.error(f"获取日志失败: {e}")
            return []
    
    def get_log_stats(self):
        """获取日志统计信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 总日志数
            cursor.execute('SELECT COUNT(*) FROM logs')
            total_logs = cursor.fetchone()[0]
            
            # 按级别统计
            cursor.execute('SELECT level, COUNT(*) FROM logs GROUP BY level')
            level_stats = dict(cursor.fetchall())
            
            # 按应用统计
            cursor.execute('SELECT app_package, COUNT(*) FROM logs GROUP BY app_package LIMIT 10')
            app_stats = dict(cursor.fetchall())
            
            # 今日日志数
            cursor.execute('SELECT COUNT(*) FROM logs WHERE DATE(created_at) = DATE("now")')
            today_logs = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total_logs': total_logs,
                'level_stats': level_stats,
                'app_stats': app_stats,
                'today_logs': today_logs
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
    
    def clear_all_logs(self):
        """清空所有日志"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM logs')
            conn.commit()
            conn.close()
            logger.info("数据库日志已清空")
            return True
        except Exception as e:
            logger.error(f"清空数据库日志失败: {e}")
            return False

# 初始化数据库
db = LogDatabase()

def process_xposed_log(raw_data, source_ip):
    """处理Xposed日志数据 - 优化文本处理"""
    try:
        # 首先尝试作为纯文本处理（大多数情况）
        message = raw_data.strip()
        
        # 初始化日志数据
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'level': 'INFO',
            'tag': 'Xposed',
            'message': message,
            'source_ip': source_ip,
            'raw_data': raw_data
        }
        
        # 智能解析日志级别（从文本中提取）
        message_lower = message.lower()
        if any(keyword in message_lower for keyword in ['error', '错误', 'exception', '异常', 'fail', '失败']):
            log_data['level'] = 'ERROR'
            log_data['tag'] = 'Error'
        elif any(keyword in message_lower for keyword in ['warn', '警告', 'warning']):
            log_data['level'] = 'WARN'
            log_data['tag'] = 'Warning'
        elif any(keyword in message_lower for keyword in ['debug', '调试']):
            log_data['level'] = 'DEBUG'
            log_data['tag'] = 'Debug'
        
        # 检测特殊标签
        if any(keyword in message_lower for keyword in ['wx', '微信', 'wechat', 'mm']):
            log_data['tag'] = 'WeChat'
            log_data['app_package'] = 'com.tencent.mm'
            log_data['data_type'] = 'wechat'
        
        # 检测敏感数据
        sensitive_keywords = [
            'phone', 'mobile', '手机', '电话',
            'token', 'auth', '认证', '令牌',
            'openid', 'userid', '用户',
            'password', '密码', 'pwd',
            '1[3-9]\\d{9}',  # 手机号正则
        ]
        
        if any(keyword in message_lower for keyword in sensitive_keywords[:8]):  # 不包括正则
            log_data['data_type'] = 'sensitive'
            log_data['level'] = 'WARN'
            log_data['tag'] = 'Sensitive'
        
        # 检查手机号正则
        import re
        if re.search(r'1[3-9]\d{9}', message):
            log_data['data_type'] = 'sensitive'
            log_data['level'] = 'WARN'
            log_data['tag'] = 'Phone'
        
        # Hook相关标签
        if any(keyword in message_lower for keyword in ['hook', 'frida', 'xposed', '拦截', '注入']):
            log_data['tag'] = 'Hook'
        
        # 最后尝试JSON解析（备用）
        if raw_data.startswith('{') and raw_data.endswith('}'):
            try:
                json_data = json.loads(raw_data)
                # 如果是JSON，合并数据
                log_data.update(json_data)
                log_data['source_ip'] = source_ip  # 保持source_ip
                log_data['raw_data'] = raw_data
            except json.JSONDecodeError:
                # JSON解析失败，继续使用文本解析结果
                pass
        
        return log_data
        
    except Exception as e:
        logger.error(f"处理日志数据失败: {e}")
        # 返回最基本的日志格式
        return {
            'timestamp': datetime.now().isoformat(),
            'level': 'ERROR',
            'tag': 'ParseError',
            'message': f'日志处理失败: {raw_data[:50]}...',
            'source_ip': source_ip,
            'raw_data': raw_data
        }

def add_log_to_system(raw_data, source_ip='unknown'):
    """添加日志到系统"""
    global log_buffer
    
    # 处理日志数据
    log_data = process_xposed_log(raw_data, source_ip)
    if not log_data:
        return
    
    # 添加到内存缓冲区
    log_buffer.append(log_data)
    if len(log_buffer) > max_buffer_size:
        log_buffer.pop(0)  # 移除最老的日志
    
    # 保存到数据库
    db.insert_log(log_data)
    
    # 实时推送到Web客户端
    if clients_count > 0:
        socketio.emit('new_log', log_data, broadcast=True)
    
    logger.info(f"新日志: [{log_data['level']}] {log_data['message'][:50]}...")

# ==================== Web路由 ====================

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/logs')
def api_logs():
    """获取日志API"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        level_filter = request.args.get('level', 'ALL')
        search_text = request.args.get('search', '')
        
        offset = (page - 1) * per_page
        
        logs = db.get_logs(
            limit=per_page, 
            offset=offset, 
            level_filter=level_filter,
            search_text=search_text
        )
        
        return jsonify({
            'success': True,
            'logs': logs,
            'page': page,
            'per_page': per_page
        })
    
    except Exception as e:
        logger.error(f"获取日志API失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stats')
def api_stats():
    """获取统计信息API"""
    try:
        stats = db.get_log_stats()
        stats['buffer_size'] = len(log_buffer)
        stats['clients_connected'] = clients_count
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    
    except Exception as e:
        logger.error(f"获取统计API失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/test')
def api_test():
    """测试API - 添加测试日志"""
    test_logs = [
        '微信Hook测试日志',
        '发现敏感数据: phone=13812345678',
        'Hook失败: java.lang.ClassNotFoundException',
        'WeChat用户登录成功',
        'error: 拦截失败',
        'warning: 检测到token传输',
        'debug: Hook点加载完成'
    ]
    
    for log_text in test_logs:
        add_log_to_system(log_text, '127.0.0.1')
    
    return jsonify({'success': True, 'message': f'已添加{len(test_logs)}条测试日志'})

@app.route('/api/clear', methods=['POST'])
def api_clear_logs():
    """清空所有日志"""
    try:
        global log_buffer
        
        # 清空内存缓冲区
        log_buffer.clear()
        
        # 清空数据库
        if not db.clear_all_logs():
            return jsonify({'success': False, 'error': '清空数据库失败'})
        
        # 通知所有客户端清空显示
        socketio.emit('clear_logs')
        
        logger.info("所有日志已清空")
        return jsonify({'success': True, 'message': '所有日志已清空'})
        
    except Exception as e:
        logger.error(f"清空日志失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ==================== WebSocket事件 ====================

@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    global clients_count
    clients_count += 1
    logger.info(f'客户端连接，当前连接数: {clients_count}')
    emit('connected', {'message': '已连接到日志服务器'})

@socketio.on('disconnect') 
def handle_disconnect():
    """客户端断开连接"""
    global clients_count
    clients_count = max(0, clients_count - 1)
    logger.info(f'客户端断开连接，当前连接数: {clients_count}')

@socketio.on('request_recent_logs')
def handle_request_recent_logs():
    """请求最近的日志"""
    recent_logs = log_buffer[-10:] if log_buffer else []
    emit('recent_logs', recent_logs)

# ==================== 启动函数 ====================

def create_directories():
    """创建必要的目录"""
    directories = ['templates', 'static/css', 'static/js', 'static/img']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

if __name__ == '__main__':
    create_directories()
    
    print("=" * 50)
    print("🚀 Xposed日志查看器启动中...")
    print("=" * 50)
    print(f"📊 Web界面: http://localhost:5000")
    print(f"📡 UDP服务: 需要单独启动 udp_server.py")
    print(f"💾 数据库: {db.db_path}")
    print("=" * 50)
    
    # 启动Web服务
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=5000, 
        debug=False,
        allow_unsafe_werkzeug=True
    ) 