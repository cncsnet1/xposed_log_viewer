#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UDP日志接收服务器
功能：接收Xposed模块通过UDP发送的日志
作者：AI助手
版本：1.0
"""

import socket
import threading
import json
import time
import logging
from datetime import datetime
import sys
import os

# 导入主应用的日志处理函数
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app import add_log_to_system

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UDPLogServer:
    """UDP日志接收服务器"""
    
    def __init__(self, host='0.0.0.0', port=9999):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        self.stats = {
            'total_received': 0,
            'total_processed': 0,
            'errors': 0,
            'clients': set(),
            'start_time': datetime.now()
        }
    
    def start(self):
        """启动UDP服务器"""
        try:
            # 创建UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # 绑定地址和端口
            self.socket.bind((self.host, self.port))
            self.running = True
            
            logger.info(f"UDP日志服务器启动成功")
            logger.info(f"监听地址: {self.host}:{self.port}")
            logger.info("等待Xposed模块发送日志...")
            
            # 启动统计线程
            stats_thread = threading.Thread(target=self._stats_reporter, daemon=True)
            stats_thread.start()
            
            # 主循环接收数据
            while self.running:
                try:
                    # 接收数据 (最大64KB)
                    data, addr = self.socket.recvfrom(65536)
                    
                    # 更新统计信息
                    self.stats['total_received'] += 1
                    self.stats['clients'].add(addr[0])
                    
                    # 处理接收到的数据
                    self._process_received_data(data, addr)
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        logger.error(f"接收数据失败: {e}")
                        self.stats['errors'] += 1
        
        except Exception as e:
            logger.error(f"启动UDP服务器失败: {e}")
            raise
        finally:
            self._cleanup()
    
    def _process_received_data(self, data, addr):
        """处理接收到的数据"""
        try:
            # 解码数据
            raw_message = data.decode('utf-8', errors='ignore')
            
            if not raw_message.strip():
                return
            
            logger.info(f"收到来自 {addr[0]}:{addr[1]} 的日志: {raw_message[:100]}...")
            
            # 处理可能的多行日志
            lines = raw_message.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if line:
                    # 直接添加原始文本到日志系统
                    add_log_to_system(line, addr[0])
                    self.stats['total_processed'] += 1
            
        except UnicodeDecodeError as e:
            logger.error(f"解码数据失败: {e}")
            # 尝试其他编码
            try:
                raw_message = data.decode('gbk', errors='ignore')
                if raw_message.strip():
                    add_log_to_system(raw_message.strip(), addr[0])
                    self.stats['total_processed'] += 1
            except:
                self.stats['errors'] += 1
        except Exception as e:
            logger.error(f"处理数据失败: {e}")
            self.stats['errors'] += 1
    
    def _stats_reporter(self):
        """定期报告统计信息"""
        while self.running:
            time.sleep(30)  # 每30秒报告一次
            
            if self.stats['total_received'] > 0:
                uptime = datetime.now() - self.stats['start_time']
                logger.info(f"=== UDP服务器统计 ===")
                logger.info(f"运行时间: {uptime}")
                logger.info(f"接收总数: {self.stats['total_received']}")
                logger.info(f"处理总数: {self.stats['total_processed']}")
                logger.info(f"错误总数: {self.stats['errors']}")
                logger.info(f"客户端数: {len(self.stats['clients'])}")
                logger.info(f"客户端IP: {', '.join(self.stats['clients'])}")
                logger.info("==================")
    
    def stop(self):
        """停止UDP服务器"""
        logger.info("正在停止UDP服务器...")
        self.running = False
        if self.socket:
            self.socket.close()
    
    def _cleanup(self):
        """清理资源"""
        if self.socket:
            self.socket.close()
            self.socket = None
        logger.info("UDP服务器已停止")

class XposedLogFormatter:
    """Xposed日志格式化器"""
    
    @staticmethod
    def format_wechat_log(message):
        """格式化微信相关日志"""
        try:
            # 检查是否是微信Hook日志的特定格式
            if '[WeChat]' in message or '[微信]' in message:
                return {
                    'level': 'INFO',
                    'tag': 'WeChat',
                    'message': message,
                    'app_package': 'com.tencent.mm',
                    'data_type': 'wechat'
                }
            
            # 检查敏感数据格式
            if any(keyword in message.lower() for keyword in ['token', 'phone', 'mobile', 'openid']):
                return {
                    'level': 'WARN',
                    'tag': 'Sensitive',
                    'message': message,
                    'data_type': 'sensitive'
                }
            
            # 默认格式
            return {
                'level': 'INFO',
                'tag': 'Xposed',
                'message': message
            }
            
        except Exception as e:
            logger.error(f"格式化日志失败: {e}")
            return None
    
    @staticmethod
    def parse_structured_log(log_string):
        """解析结构化日志"""
        try:
            # 尝试解析JSON格式
            if log_string.startswith('{') and log_string.endswith('}'):
                return json.loads(log_string)
            
            # 尝试解析自定义格式: [LEVEL] TAG: MESSAGE
            import re
            pattern = r'\[(\w+)\]\s*(\w+):\s*(.*)'
            match = re.match(pattern, log_string)
            
            if match:
                level, tag, message = match.groups()
                return {
                    'level': level.upper(),
                    'tag': tag,
                    'message': message
                }
            
            # 无法解析，返回原始格式  
            return {
                'level': 'INFO',
                'tag': 'Raw',
                'message': log_string
            }
            
        except Exception as e:
            logger.error(f"解析结构化日志失败: {e}")
            return None

def create_test_client():
    """创建测试客户端，用于测试UDP服务器"""
    def send_test_logs():
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            test_logs = [
                '微信Hook初始化完成',
                '发现手机号: 13812345678',
                'Hook失败: ClassNotFoundException',
                '拦截到微信登录操作',
                'WeChat获取用户信息: openid=ox1234567',
                'error: 无法找到目标方法',
                'warning: 检测到敏感数据传输',
                'debug: Hook点注册成功',
                'Frida注入成功，开始监控微信',
                'token获取成功: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
            ]
            
            for i, log in enumerate(test_logs):
                test_socket.sendto(log.encode('utf-8'), ('127.0.0.1', 9999))
                print(f"发送测试日志 {i+1}: {log}")
                time.sleep(1)
            
            test_socket.close()
            print("测试日志发送完成")
            
        except Exception as e:
            print(f"发送测试日志失败: {e}")
    
    return send_test_logs

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='UDP日志接收服务器')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址 (默认: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=9999, help='监听端口 (默认: 9999)')
    parser.add_argument('--test', action='store_true', help='运行测试模式')
    
    args = parser.parse_args()
    
    if args.test:
        print("启动测试模式...")
        # 启动服务器
        server = UDPLogServer(args.host, args.port)
        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        
        # 等待服务器启动
        time.sleep(2)
        
        # 发送测试日志
        test_client = create_test_client()
        test_client()
        
        # 保持服务器运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.stop()
    else:
        # 正常启动服务器
        server = UDPLogServer(args.host, args.port)
        
        try:
            server.start()
        except KeyboardInterrupt:
            logger.info("收到中断信号")
            server.stop()
        except Exception as e:
            logger.error(f"服务器运行失败: {e}")
            server.stop()
            sys.exit(1) 