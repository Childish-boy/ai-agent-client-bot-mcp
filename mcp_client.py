"""
MCP 客户端 - 用于远程调用 FastMCP 天气服务
通过 SSE (Server-Sent Events) 协议连接到远程 MCP 服务器
"""
import json
import requests
import uuid
import threading
import time
from typing import Optional, Dict, Any
from queue import Queue


class MCPWeatherClient:
    """MCP 天气服务客户端 - 支持 SSE 长连接"""
    
    def __init__(self, server_url: str = "http://localhost:8001"):
        """
        初始化 MCP 客户端
        
        Args:
            server_url: MCP 服务器地址（SSE模式）
        """
        self.server_url = server_url.rstrip('/')
        self.session = requests.Session()
        self.response_queue = Queue()
        self.message_endpoint = None  # 服务器分配的消息端点
        self.sse_thread = None
        self._start_sse_connection()
        print(f"🔗 [MCP客户端] 初始化会话完成")
    
    def _start_sse_connection(self):
        """启动 SSE 长连接"""
        def sse_listener():
            try:
                endpoint = f"{self.server_url}/sse"
                response = self.session.get(
                    endpoint,
                    headers={
                        "Accept": "text/event-stream",
                        "Cache-Control": "no-cache"
                    },
                    stream=True,
                    timeout=None
                )
                
                # 读取 SSE 流
                current_event = None
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        
                        # 解析 SSE 事件类型
                        if line_str.startswith('event: '):
                            current_event = line_str[7:].strip()
                        elif line_str.startswith('data: '):
                            data_str = line_str[6:]
                            
                            # 如果是 endpoint 事件，保存消息端点
                            if current_event == 'endpoint':
                                self.message_endpoint = data_str
                                print(f"📍 [MCP客户端] 收到服务器端点: {self.message_endpoint}")
                            # 如果是 message 事件，解析 JSON 并放入队列
                            elif current_event == 'message':
                                try:
                                    data = json.loads(data_str)
                                    self.response_queue.put(data)
                                except:
                                    pass
                            
                            current_event = None
                                
            except Exception as e:
                print(f"⚠️ [MCP客户端] SSE 连接错误: {e}")
        
        # 启动后台线程监听 SSE
        self.sse_thread = threading.Thread(target=sse_listener, daemon=True)
        self.sse_thread.start()
        
        # 等待服务器发送 endpoint
        timeout = 5
        start_time = time.time()
        while self.message_endpoint is None and time.time() - start_time < timeout:
            time.sleep(0.1)
        
        if self.message_endpoint is None:
            print(f"⚠️ [MCP客户端] 未收到服务器端点")
        else:
            print(f"✅ [MCP客户端] SSE 连接建立成功")
            # 发送 MCP 初始化请求
            self._initialize_mcp()
    
    def _initialize_mcp(self):
        """发送 MCP 初始化请求"""
        try:
            endpoint = f"{self.server_url}{self.message_endpoint}"
            
            # 构造 MCP 初始化请求
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {
                            "listChanged": False
                        }
                    },
                    "clientInfo": {
                        "name": "mcp-weather-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            # 发送初始化请求
            response = self.session.post(
                endpoint,
                json=init_request,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            if response.status_code in [200, 202]:
                # 等待初始化响应
                timeout = 5
                start_time = time.time()
                while time.time() - start_time < timeout:
                    if not self.response_queue.empty():
                        init_response = self.response_queue.get()
                        if init_response.get("id") == 1:
                            print(f"✅ [MCP客户端] MCP 协议初始化完成")
                            
                            # 发送 initialized 通知
                            initialized_notification = {
                                "jsonrpc": "2.0",
                                "method": "notifications/initialized"
                            }
                            self.session.post(
                                endpoint,
                                json=initialized_notification,
                                headers={"Content-Type": "application/json"},
                                timeout=5
                            )
                            return
                    time.sleep(0.1)
                
                print(f"⚠️ [MCP客户端] 初始化响应超时")
            else:
                print(f"⚠️ [MCP客户端] 初始化请求失败: {response.status_code}")
                
        except Exception as e:
            print(f"⚠️ [MCP客户端] 初始化错误: {e}")
        
    def _call_tool(self, tool_name: str, arguments: dict) -> dict:
        """
        调用 MCP 工具（通过 SSE 消息端点）
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        try:
            # 检查是否已获取到消息端点
            if self.message_endpoint is None:
                return {
                    "success": False,
                    "error": "MCP 连接未建立"
                }
            
            # 使用服务器分配的消息端点（包含 session_id）
            # message_endpoint 已经是完整路径（带前导斜杠），直接拼接
            endpoint = f"{self.server_url}{self.message_endpoint}"
            
            # 构造 MCP 请求消息（JSON-RPC 2.0）
            request_id = str(uuid.uuid4())
            mcp_request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            # 发送请求到 MCP 服务器（通过 POST，响应会从 SSE 返回）
            response = self.session.post(
                endpoint,
                json=mcp_request,
                headers={
                    "Content-Type": "application/json"
                },
                timeout=5
            )
            
            if response.status_code != 200 and response.status_code != 202:
                return {
                    "success": False,
                    "error": f"MCP服务器返回错误: {response.status_code} - {response.text}"
                }
            
            # 从 SSE 队列中等待响应
            timeout = 30
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                if not self.response_queue.empty():
                    mcp_response = self.response_queue.get()
                    
                    # 检查是否是对应的响应
                    if mcp_response.get("id") == request_id:
                        # 检查是否有错误
                        if "error" in mcp_response:
                            return {
                                "success": False,
                                "error": mcp_response["error"].get("message", "未知错误")
                            }
                        
                        # 提取工具返回的结果
                        result = mcp_response.get("result", {})
                        
                        # FastMCP 的工具返回结果在 content 字段中
                        if "content" in result and len(result["content"]) > 0:
                            content_item = result["content"][0]
                            if content_item.get("type") == "text":
                                # 解析 JSON 文本
                                return json.loads(content_item.get("text", "{}"))
                        
                        return {
                            "success": False,
                            "error": "无法解析MCP响应"
                        }
                
                time.sleep(0.1)
            
            return {
                "success": False,
                "error": "等待MCP响应超时"
            }
            
        except requests.Timeout:
            return {
                "success": False,
                "error": "MCP服务器请求超时"
            }
        except requests.ConnectionError:
            return {
                "success": False,
                "error": f"无法连接到MCP服务器: {self.server_url}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"MCP调用失败: {str(e)}"
            }
    
    def query_current_weather(self, city: str) -> dict:
        """
        查询实时天气
        
        Args:
            city: 城市名称
            
        Returns:
            天气数据字典
        """
        print(f"🔄 [MCP客户端] 调用远程服务: query_current_weather")
        print(f"   - 服务器: {self.server_url}")
        print(f"   - 城市: {city}")
        
        result = self._call_tool("query_current_weather", {"city": city})
        
        if result.get("success"):
            print(f"✅ [MCP客户端] 调用成功!")
        else:
            print(f"❌ [MCP客户端] 调用失败: {result.get('error')}")
        
        return result
    
    def query_weather_forecast(self, city: str) -> dict:
        """
        查询天气预报
        
        Args:
            city: 城市名称
            
        Returns:
            天气预报数据字典
        """
        print(f"🔄 [MCP客户端] 调用远程服务: query_weather_forecast")
        print(f"   - 服务器: {self.server_url}")
        print(f"   - 城市: {city}")
        
        result = self._call_tool("query_weather_forecast", {"city": city})
        
        if result.get("success"):
            print(f"✅ [MCP客户端] 调用成功! (预报{result.get('days', 0)}天)")
        else:
            print(f"❌ [MCP客户端] 调用失败: {result.get('error')}")
        
        return result


# 全局客户端实例
_mcp_client: Optional[MCPWeatherClient] = None


def get_mcp_client(server_url: str = "http://localhost:8001") -> MCPWeatherClient:
    """
    获取 MCP 客户端实例（单例模式）
    
    Args:
        server_url: MCP 服务器地址
        
    Returns:
        MCP 客户端实例
    """
    global _mcp_client
    
    if _mcp_client is None:
        _mcp_client = MCPWeatherClient(server_url)
        print(f"🌐 [MCP客户端] 初始化连接: {server_url}")
    
    return _mcp_client


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("🧪 MCP 客户端测试")
    print("=" * 60)
    print()
    
    client = get_mcp_client()
    
    # 测试实时天气
    print("📍 测试1: 查询北京实时天气")
    result = client.query_current_weather("北京")
    print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    print()
    
    # 测试天气预报
    print("📍 测试2: 查询上海天气预报")
    result = client.query_weather_forecast("上海")
    print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    print()
    
    print("=" * 60)

