"""Run/resume one account run, with the 5-minute run budget and Postgres or in-memory checkpoints."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from revops_ai.graph.graph import Deps, build_graph
from revops_ai.graph.state import RunState

RUN_BUDGET_S = 300.0


@asynccontextmanager
async def checkpointer(dsn: str | None = None) -> AsyncIterator[BaseCheckpointSaver[Any]]:
    """Postgres saver when a DSN is given (tables created in the AI service's own schema/database)."""
    if not dsn:
        yield MemorySaver()
        return
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        await saver.setup()
        yield saver


class AccountRunner:
    def __init__(
        self, deps: Deps, saver: BaseCheckpointSaver[Any] | None, budget_s: float = RUN_BUDGET_S
    ) -> None:
        self.deps, self.budget = deps, budget_s
        self.graph = build_graph(deps, saver)

    @staticmethod
    def _cfg(run_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": f"run:{run_id}"}}

    async def run(
        self,
        org_id: str,
        account_id: str,
        run_id: str,
        trigger: str = "manual",
        *,
        thread_id: str | None = None,
    ) -> RunState:
        """`run_id` is what status reports are posted to; `thread_id` (default: the run id) names
        the checkpoint thread, so several findings can be explained under one backend run."""
        init: RunState = {
            "org_id": org_id,
            "account_id": account_id,
            "run_id": run_id,
            "trigger": trigger,
        }
        thread = thread_id or run_id
        try:
            await asyncio.wait_for(self.graph.ainvoke(init, self._cfg(thread)), self.budget)
        except TimeoutError:
            await self.deps.backend.run_status(org_id, run_id, "failed", {}, "run budget exceeded")
            return {**init, "status": "failed", "error": "run budget exceeded"}
        return await self.state(thread)

    async def forget(self, thread_id: str, run_id: str | None = None) -> None:
        """Drop everything kept for a finished run (checkpoints, cached context, traces)."""
        for store in (self.deps.cache, self.deps.metas, self.deps.traces):
            store.pop(run_id or thread_id, None)
        saver = self.graph.checkpointer
        drop = getattr(saver, "adelete_thread", None)
        if drop is not None:
            try:
                await drop(f"run:{thread_id}")
            except Exception:  # noqa: BLE001 - cleanup only
                pass

    async def resume(self, run_id: str, decisions: dict[str, str]) -> RunState:
        await asyncio.wait_for(self.graph.ainvoke(Command(resume={"decisions": decisions}), self._cfg(run_id)), self.budget)  # fmt: skip
        return await self.state(run_id)

    async def state(self, run_id: str) -> RunState:
        snap = await self.graph.aget_state(self._cfg(run_id))
        out: RunState = dict(snap.values)  # type: ignore[assignment]
        if snap.next:  # interrupted: waiting for approval
            out["status"] = "waiting_approval"
        return out

    def is_waiting(self, st: RunState) -> bool:
        return st.get("status") == "waiting_approval"
