#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Xposed日志查看器 - 一键启动脚本
同时启动Web服务和UDP服务器
"""

import os
import sys
import time
import threading
import subprocess
import signal
from multiprocessing import Process

class XposedLogViewer:
    """Xposed日志查看器主控制器"""
    
    def __init__(self):
        self.web_process = None
        self.udp_process = None
        self.running = False
    
    def start_web_server(self):
        """启动Web服务器"""
        try:
            print("🌐 启动Web服务器...")
            os.system("python app.py")
        except Exception as e:
            print(f"❌ Web服务器启动失败: {e}")
    
    def start_udp_server(self):
        """启动UDP服务器"""
        try:
            print("📡 启动UDP服务器...")
            os.system("python udp_server.py")
        except Exception as e:
            print(f"❌ UDP服务器启动失败: {e}")
    
    def start(self):
        """启动所有服务"""
        self.running = True
        
        print("=" * 60)
        print("🚀 Xposed日志查看器启动中...")
        print("=" * 60)
        
        try:
            # 启动UDP服务器进程
            self.udp_process = Process(target=self.start_udp_server)
            self.udp_process.daemon = True
            self.udp_process.start()
            
            # 等待UDP服务器启动
            time.sleep(2)
            
            # 启动Web服务器进程
            self.web_process = Process(target=self.start_web_server)
            self.web_process.daemon = True
            self.web_process.start()
            
            print("✅ 所有服务启动完成!")
            print("📊 Web界面: http://localhost:5000")
            print("📡 UDP接收: localhost:9999")
            print("💡 按 Ctrl+C 停止所有服务")
            print("=" * 60)
            
            # 保持主进程运行
            while self.running:
                time.sleep(1)
                
                # 检查进程状态
                if self.web_process and not self.web_process.is_alive():
                    print("⚠️  Web服务器进程异常退出")
                    break
                    
                if self.udp_process and not self.udp_process.is_alive():
                    print("⚠️  UDP服务器进程异常退出")
                    break
        
        except KeyboardInterrupt:
            print("\n🛑 收到停止信号...")
            self.stop()
        except Exception as e:
            print(f"❌ 启动失败: {e}")
            self.stop()
    
    def stop(self):
        """停止所有服务"""
        self.running = False
        
        print("🛑 正在停止所有服务...")
        
        if self.web_process and self.web_process.is_alive():
            print("🌐 停止Web服务器...")
            self.web_process.terminate()
            self.web_process.join(timeout=5)
        
        if self.udp_process and self.udp_process.is_alive():
            print("📡 停止UDP服务器...")
            self.udp_process.terminate()
            self.udp_process.join(timeout=5)
        
        print("✅ 所有服务已停止")

def check_dependencies():
    """检查依赖是否安装"""
    required_packages = ['flask', 'flask_socketio']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ 缺少依赖包:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n💡 请运行: pip install -r requirements.txt")
        return False
    
    return True

def create_xposed_module_template():
    """创建Xposed模块示例代码"""
    template = '''
// Xposed模块发送日志示例代码
public class LogSender {
    private static final String LOG_SERVER_IP = "192.168.1.100";  // 修改为你的服务器IP
    private static final int LOG_SERVER_PORT = 9999;
    
    public static void sendLog(String level, String tag, String message) {
        try {
            DatagramSocket socket = new DatagramSocket();
            
            // 构建JSON格式的日志
            JSONObject logData = new JSONObject();
            logData.put("level", level);
            logData.put("tag", tag);
            logData.put("message", message);
            logData.put("timestamp", System.currentTimeMillis());
            logData.put("app_package", "com.tencent.mm");  // 目标应用包名
            
            String jsonString = logData.toString();
            byte[] data = jsonString.getBytes("UTF-8");
            
            DatagramPacket packet = new DatagramPacket(
                data, data.length, 
                InetAddress.getByName(LOG_SERVER_IP), 
                LOG_SERVER_PORT
            );
            
            socket.send(packet);
            socket.close();
            
        } catch (Exception e) {
            XposedBridge.log("发送日志失败: " + e.getMessage());
        }
    }
    
    // 使用示例
    public void hookMethod() {
        // 在Hook的方法中调用
        sendLog("INFO", "WeChat", "微信方法被调用");
        sendLog("WARN", "Sensitive", "发现敏感数据: " + sensitiveData);
    }
}
'''
    
    with open('xposed_module_template.java', 'w', encoding='utf-8') as f:
        f.write(template)
    
    print("📝 已创建Xposed模块示例代码: xposed_module_template.java")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Xposed日志查看器启动器')
    parser.add_argument('--check', action='store_true', help='检查依赖')
    parser.add_argument('--template', action='store_true', help='创建Xposed模块模板')
    parser.add_argument('--web-only', action='store_true', help='只启动Web服务')
    parser.add_argument('--udp-only', action='store_true', help='只启动UDP服务')
    
    args = parser.parse_args()
    
    if args.check:
        if check_dependencies():
            print("✅ 所有依赖已安装")
        sys.exit(0)
    
    if args.template:
        create_xposed_module_template()
        sys.exit(0)
    
    if args.web_only:
        print("🌐 只启动Web服务器...")
        os.system("python app.py")
        sys.exit(0)
    
    if args.udp_only:
        print("📡 只启动UDP服务器...")
        os.system("python udp_server.py")
        sys.exit(0)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 启动所有服务
    viewer = XposedLogViewer()
    viewer.start() 