from typing import Any

from app.agents.memory_policy import MEMORY_LABELS, parse_memory_command
from app.observability.langsmith import add_trace_metadata
from app.repositories.user_memory_repository import UserMemoryRepository


def _memory_label(key: str) -> str:
    return MEMORY_LABELS.get(key, key.replace("_", " "))


def memory_agent(state: dict[str, Any]) -> dict[str, Any]:
    command = parse_memory_command(state["query"])
    if command is None:
        add_trace_metadata(memory_action="unrecognized", memory_status="rejected")
        return {"memory_output": "That memory request could not be understood."}
    if command.action == "reject":
        add_trace_metadata(memory_action="reject", memory_status="rejected")
        return {"memory_output": command.error or "That memory cannot be stored."}

    repository = UserMemoryRepository(state["db"])
    user_id = state["user_id"]
    if command.action == "store":
        repository.upsert(
            user_id=user_id,
            memory_key=command.key,
            memory_value=command.value,
            memory_type=command.memory_type,
            source_conversation_id=state.get("conversation_id"),
            source_message_id=state.get("current_message_id"),
        )
        add_trace_metadata(
            memory_action="store",
            memory_key=command.key,
            memory_type=command.memory_type,
            memory_status="success",
        )
        return {
            "memory_output": (
                f"I'll remember that your {_memory_label(command.key)} "
                f"is {command.value}."
            ),
            "observability": {
                "memory_action": "store",
                "memory_key": command.key,
                "memory_status": "success",
            },
        }

    if command.action == "forget":
        deleted = repository.forget(user_id, command.key)
        if deleted:
            message = f"I've forgotten your {_memory_label(command.key)}."
        else:
            message = f"I did not have your {_memory_label(command.key)} saved."
        add_trace_metadata(
            memory_action="forget",
            memory_key=command.key,
            memory_status="success" if deleted else "not_found",
        )
        return {
            "memory_output": message,
            "observability": {
                "memory_action": "forget",
                "memory_key": command.key,
                "memory_status": "success" if deleted else "not_found",
            },
        }

    if command.action == "forget_all":
        count = repository.forget_all(user_id)
        message = (
            "I've forgotten all saved information about you."
            if count
            else "I did not have any saved information about you."
        )
        add_trace_metadata(
            memory_action="forget_all",
            memory_status="success",
            affected_memory_count=count,
        )
        return {
            "memory_output": message,
            "observability": {
                "memory_action": "forget_all",
                "affected_memory_count": count,
            },
        }

    memories = repository.list_active(user_id)
    add_trace_metadata(
        memory_action="list",
        memory_status="success",
        retrieved_memory_count=len(memories),
        retrieved_memory_keys=[memory.memory_key for memory in memories],
    )
    if not memories:
        return {
            "memory_output": "I do not have any saved information about you.",
            "observability": {
                "memory_action": "list",
                "retrieved_memory_count": 0,
            },
        }
    details = "; ".join(
        f"{_memory_label(memory.memory_key)}: {memory.memory_value}"
        for memory in memories
    )
    return {
        "memory_output": f"I remember: {details}.",
        "observability": {
            "memory_action": "list",
            "retrieved_memory_count": len(memories),
            "retrieved_memory_keys": [memory.memory_key for memory in memories],
        },
    }
