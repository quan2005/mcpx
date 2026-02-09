"""工具和资源描述生成。

将描述生成逻辑从 __main__.py 提取到独立模块。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcpx.server import ServerManager


__all__ = ["generate_tools_description", "generate_resources_description"]


def generate_tools_description(manager: "ServerManager") -> str:
    """生成所有可用工具的紧凑描述。

    格式: server.tool(param, param?): description

    Args:
        manager: 已初始化的 ServerManager

    Returns:
        格式化后的工具描述字符串
    """
    tools_desc_lines = ["Available tools:"]

    for server_name in sorted(manager.list_servers()):
        for tool in manager.list_tools(server_name):
            # 从 input_schema 提取参数列表
            params = []
            properties = tool.input_schema.get("properties", {})
            required = set(tool.input_schema.get("required", []))

            for param_name in sorted(properties.keys()):
                # 必填参数直接显示，可选参数加 ?
                params.append(param_name if param_name in required else f"{param_name}?")

            params_str = ", ".join(params) if params else ""

            # 截断过长的描述（60 字符）
            desc = tool.description
            if len(desc) > 60:
                desc = desc[:57] + "..."

            # 格式: server.tool(params): desc
            full_name = f"{server_name}.{tool.name}"
            if params_str:
                tools_desc_lines.append(f"  - {full_name}({params_str}): {desc}")
            else:
                tools_desc_lines.append(f"  - {full_name}: {desc}")

    return "\n".join(tools_desc_lines)


def generate_resources_description(manager: "ServerManager") -> str:
    """生成所有可用资源的紧凑描述。

    Args:
        manager: 已初始化的 ServerManager

    Returns:
        格式化后的资源描述字符串
    """
    resources_desc_lines = ["Available resources:"]

    for server_name in sorted(manager.list_servers()):
        resources = manager.list_resources(server_name)
        if not resources:
            continue

        # 获取服务器信息用于描述
        server_info = manager.get_server_info(server_name)
        if server_info and server_info.instructions:
            server_desc = server_info.instructions
            if len(server_desc) > 300:
                server_desc = server_desc[:297] + "..."
            resources_desc_lines.append(f"  Server: {server_name} - {server_desc}")
        else:
            resources_desc_lines.append(f"  Server: {server_name}")

        for resource in resources:
            # 构建资源信息行
            mime_info = f" [{resource.mime_type}]" if resource.mime_type else ""
            size_info = f" ({resource.size} bytes)" if resource.size is not None else ""

            # 截断过长的描述（80 字符）
            desc = ""
            if resource.description:
                desc_text = resource.description
                if len(desc_text) > 80:
                    desc_text = desc_text[:77] + "..."
                desc = f": {desc_text}"

            resources_desc_lines.append(
                f"    - {resource.name} ({resource.uri}){mime_info}{size_info}{desc}"
            )

    return (
        "\n".join(resources_desc_lines)
        if len(resources_desc_lines) > 1
        else "No resources available."
    )
