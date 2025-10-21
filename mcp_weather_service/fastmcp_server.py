import os
import requests
from typing import Optional
from mcp.server.fastmcp import FastMCP

# 高德地图 API Key
AMAP_API_KEY = "xxx"

# 创建 FastMCP 服务器实例（配置 HTTP 端口和主机）
mcp = FastMCP(
    "天气查询服务-FastMCP",
    host="0.0.0.0",  # 允许远程访问
    port=8001,       # 服务端口
    stateless_http=True  # 启用无状态 HTTP 模式
)


def get_city_code(city_name: str) -> Optional[str]:
    """
    获取城市的 adcode 编码
    
    Args:
        city_name: 城市名称，如：北京、上海、广州
    
    Returns:
        城市编码，如果未找到返回 None
    """
    url = "https://restapi.amap.com/v3/config/district"
    params = {
        "key": AMAP_API_KEY,
        "keywords": city_name,
        "subdistrict": 0
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        result = response.json()
        
        if result.get("status") == "1" and result.get("districts"):
            adcode = result["districts"][0]["adcode"]
            print(f"🗺️  城市编码: {city_name} → {adcode}")
            return adcode
        else:
            print(f"❌ 未找到城市: {city_name}")
            return None
    except Exception as e:
        print(f"❌ 获取城市编码失败: {e}")
        return None


@mcp.tool()
def query_current_weather(city: str) -> dict:
    """
    查询指定城市的实时天气信息
    
    Args:
        city: 城市名称，如：北京、上海、广州
    
    Returns:
        实时天气数据字典，包含：
        - success: 是否成功
        - city: 城市名称
        - weather: 天气状况（晴、多云、阴、雨等）
        - temperature: 温度（°C）
        - winddirection: 风向
        - windpower: 风力等级
        - humidity: 湿度（%）
        - reporttime: 数据更新时间
    """
    print(f"\n{'='*60}")
    print(f"🌤️  [MCP工具调用] query_current_weather")
    print(f"📍 城市: {city}")
    print(f"{'='*60}\n")
    
    # 获取城市编码
    city_code = get_city_code(city)
    if not city_code:
        return {
            "success": False,
            "error": f"未找到城市: {city}"
        }
    
    # 查询实时天气
    weather_url = "https://restapi.amap.com/v3/weather/weatherInfo"
    params = {
        "key": AMAP_API_KEY,
        "city": city_code,
        "extensions": "base"  # base=实时天气
    }
    
    try:
        response = requests.get(weather_url, params=params, timeout=10)
        result = response.json()
        
        if result.get("status") != "1":
            return {
                "success": False,
                "error": "高德地图 API 返回错误"
            }
        
        lives = result.get("lives", [])
        if not lives:
            return {
                "success": False,
                "error": "未获取到天气数据"
            }
        
        weather_data = lives[0]
        
        # 标准化返回结果
        result_data = {
            "success": True,
            "type": "current",
            "city": weather_data.get("city"),
            "weather": weather_data.get("weather"),
            "temperature": weather_data.get("temperature"),
            "winddirection": weather_data.get("winddirection"),
            "windpower": weather_data.get("windpower"),
            "humidity": weather_data.get("humidity"),
            "reporttime": weather_data.get("reporttime")
        }
        
        print(f"✅ 查询成功!")
        print(f"   城市: {result_data['city']}")
        print(f"   天气: {result_data['weather']}")
        print(f"   温度: {result_data['temperature']}°C")
        print(f"   湿度: {result_data['humidity']}%\n")
        
        return result_data
        
    except Exception as e:
        print(f"❌ 查询失败: {e}\n")
        return {
            "success": False,
            "error": f"查询天气时发生错误: {str(e)}"
        }


@mcp.tool()
def query_weather_forecast(city: str) -> dict:
    """
    查询指定城市的未来天气预报
    
    Args:
        city: 城市名称，如：北京、上海、广州
    
    Returns:
        天气预报数据字典，包含：
        - success: 是否成功
        - type: "forecast"
        - city: 城市名称
        - forecasts: 预报列表，每项包含：
            - date: 日期（YYYY-MM-DD）
            - week: 星期
            - dayweather: 白天天气
            - nightweather: 夜间天气
            - daytemp: 白天温度
            - nighttemp: 夜间温度
            - daywind: 白天风向
            - nightwind: 夜间风向
    """
    print(f"\n{'='*60}")
    print(f"📅 [MCP工具调用] query_weather_forecast")
    print(f"📍 城市: {city}")
    print(f"{'='*60}\n")
    
    # 获取城市编码
    city_code = get_city_code(city)
    if not city_code:
        return {
            "success": False,
            "error": f"未找到城市: {city}"
        }
    
    # 查询天气预报
    weather_url = "https://restapi.amap.com/v3/weather/weatherInfo"
    params = {
        "key": AMAP_API_KEY,
        "city": city_code,
        "extensions": "all"  # all=预报天气
    }
    
    try:
        response = requests.get(weather_url, params=params, timeout=10)
        result = response.json()
        
        if result.get("status") != "1":
            return {
                "success": False,
                "error": "高德地图 API 返回错误"
            }
        
        forecasts = result.get("forecasts", [])
        if not forecasts:
            return {
                "success": False,
                "error": "未获取到预报数据"
            }
        
        forecast_data = forecasts[0]
        casts = forecast_data.get("casts", [])
        
        # 格式化预报数据
        forecast_list = []
        for cast in casts:
            forecast_list.append({
                "date": cast.get("date"),
                "week": cast.get("week"),
                "dayweather": cast.get("dayweather"),
                "nightweather": cast.get("nightweather"),
                "daytemp": cast.get("daytemp"),
                "nighttemp": cast.get("nighttemp"),
                "daywind": cast.get("daywind"),
                "nightwind": cast.get("nightwind")
            })
        
        result_data = {
            "success": True,
            "type": "forecast",
            "city": forecast_data.get("city"),
            "forecasts": forecast_list,
            "days": len(forecast_list)
        }
        
        print(f"✅ 查询成功!")
        print(f"   城市: {result_data['city']}")
        print(f"   预报天数: {result_data['days']}天")
        for i, forecast in enumerate(forecast_list, 1):
            print(f"   第{i}天: {forecast['date']} ({forecast['week']}) {forecast['dayweather']}/{forecast['nightweather']}")
        print()
        
        return result_data
        
    except Exception as e:
        print(f"❌ 查询失败: {e}\n")
        return {
            "success": False,
            "error": f"查询天气预报时发生错误: {str(e)}"
        }


if __name__ == "__main__":
    import sys
    
    print("=" * 80)
    print("🌤️  FastMCP 天气查询服务")
    print("=" * 80)
    print()
    print("📡 服务信息:")
    print("   - 数据源: 高德地图 API")
    print("   - 协议: MCP (Model Context Protocol)")
    print()
    print("🔧 可用工具:")
    print("   1. query_current_weather(city) - 查询实时天气")
    print("   2. query_weather_forecast(city) - 查询未来天气预报")
    print()
    
    # 检查是否以 SSE 模式运行
    if len(sys.argv) > 1 and sys.argv[1] == "--sse":
        print("🌐 运行模式: SSE (Server-Sent Events) - 支持远程长连接")
        print("   - 端口: 8001")
        print("   - 本地访问: http://localhost:8001")
        print("   - 远程访问: http://你的IP:8001")
        print("   - SSE 端点: /sse")
        print("   - 消息端点: /messages/")
        print()
        print("=" * 80)
        print("✅ MCP 服务器启动中 (SSE模式)...")
        print("=" * 80)
        print()
        
        # 运行 FastMCP 服务器（SSE 模式，端口和主机在实例化时已配置）
        mcp.run(transport="sse")
    else:
        print("🌐 运行模式: STDIO - 用于 MCP Inspector 调试")
        print("   调试命令: npx @modelcontextprotocol/inspector python fastmcp_server.py")
        print()
        print("=" * 80)
        print("✅ MCP 服务器启动中 (STDIO模式)...")
        print("=" * 80)
        print()
        
        # 运行 FastMCP 服务器（stdio 模式，配合 Inspector 使用）
        mcp.run(transport="stdio")

