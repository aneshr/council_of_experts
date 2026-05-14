from .router_chat import (
    RouterChatState,
    router_node,
    fallback_node,
    stream_expert_node,
    route_after_router,
)
from langgraph.graph import StateGraph, END

graph = StateGraph(RouterChatState)
graph.add_node("router", router_node)
graph.add_node("fallback", fallback_node)
graph.add_node("stream_expert", stream_expert_node)
graph.set_entry_point("router")
# When an expert is chosen, run stream_expert (node passes config so stream_mode="messages" streams tokens).
graph.add_conditional_edges("router", route_after_router, ["fallback", "stream_expert"])
graph.add_edge("fallback", END)
graph.add_edge("stream_expert", END)

router_chat_app = graph.compile()

__all__ = [
    "RouterChatState",
    "router_node",
    "fallback_node",
    "stream_expert_node",
    "route_after_router",
    "router_chat_app",
]

