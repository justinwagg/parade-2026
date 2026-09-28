import asyncio
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ActionDef:
    type: str
    params: dict = field(default_factory=dict)


@dataclass
class TriggerDef:
    event_type: str
    condition: str | None = None


@dataclass
class CueDef:
    id: str
    trigger: TriggerDef
    actions: list[ActionDef]
    priority: int = 10
    cooldown_ms: float = 0
    description: str = ""
    _last_triggered: float = field(default=0.0, init=False, repr=False)


class ShowEngine:
    def __init__(self, event_bus, scene_manager, cues: list[dict],
                 relay_manager=None, pixel_manager=None, state_machine=None,
                 groups: list | None = None):
        self._event_bus = event_bus
        self._scene_manager = scene_manager
        self._relay_manager = relay_manager
        self._pixel_manager = pixel_manager
        self._state_machine = state_machine
        self._cues: list[CueDef] = []
        self._load_cues(cues)
        # Fixture groups: group_id -> [fixture_id, ...]
        self._groups: dict[str, list[str]] = {}
        if groups:
            self._load_groups(groups)
        # Live progress — read by state_snapshot
        self.active_cue: str | None = None
        self.active_step: int = 0
        self.total_steps: int = 0
        self.active_label: str = ""
        # Shared flag store — set/read by cue actions and trigger conditions
        self._vars: dict = {}
        self._tasks: set[asyncio.Task] = set()

    def _load_cues(self, cues_data: list[dict]) -> None:
        for d in cues_data:
            trigger_data = d.get("trigger", {})
            trigger = TriggerDef(
                event_type=trigger_data.get("event", ""),
                condition=trigger_data.get("condition"),
            )
            actions = [
                ActionDef(
                    type=a["type"],
                    params={k: v for k, v in a.items() if k != "type"},
                )
                for a in d.get("actions", [])
            ]
            cue = CueDef(
                id=d["id"],
                trigger=trigger,
                actions=actions,
                priority=d.get("priority", 10),
                cooldown_ms=d.get("cooldown_ms", 0),
                description=d.get("description", ""),
            )
            self._cues.append(cue)
        logger.info("Loaded %d cues", len(self._cues))

    async def start(self) -> None:
        self._event_bus.subscribe("gpio_changed", self._handle_event)
        self._event_bus.subscribe("operator_trigger", self._handle_event)
        self._event_bus.subscribe("rotation_index", self._handle_event)
        logger.info("Show engine started")

    async def stop(self) -> None:
        await self.cancel_all()
        logger.info("Show engine stopped")

    async def cancel_all(self) -> None:
        """Cancel every running cue and wait for them to unwind."""
        tasks = [t for t in self._tasks if not t.done()]
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("Cancelled %d running cue(s)", len(tasks))

    def list_cues(self) -> list[dict]:
        return [
            {
                "id": cue.id,
                "description": cue.description,
                "trigger": {
                    "event": cue.trigger.event_type,
                    "condition": cue.trigger.condition,
                },
                "actions": [{"type": a.type, **a.params} for a in cue.actions],
                "cooldown_ms": cue.cooldown_ms,
                "priority": cue.priority,
            }
            for cue in self._cues
        ]

    def _evaluate_condition(self, condition: str | None, event) -> bool:
        if not condition:
            return True
        try:
            ctx = {"event": event, "vars": self._vars, "true": True, "false": False, "null": None}
            result = eval(condition, {"__builtins__": {}}, ctx)
            return bool(result)
        except Exception as e:
            logger.warning("Condition eval error (%r): %s", condition, e)
            return False

    async def _handle_event(self, event) -> None:
        from parade.core.state import SystemState
        if self._state_machine is not None:
            if self._state_machine.state != SystemState.RUNNING:
                logger.debug(
                    "Event %s ignored — engine not RUNNING (state=%s)",
                    event.event_type, self._state_machine.state,
                )
                return
        now = time.time()
        for cue in self._cues:
            if cue.trigger.event_type != event.event_type:
                continue
            if (
                cue.cooldown_ms > 0
                and (now - cue._last_triggered) * 1000 < cue.cooldown_ms
            ):
                continue
            if not self._evaluate_condition(cue.trigger.condition, event):
                continue
            cue._last_triggered = now
            task = asyncio.create_task(self._execute_cue(cue, event))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _execute_cue(self, cue: CueDef, event) -> None:
        from parade.core.events import CueStartedEvent, CueCompletedEvent, CueCancelledEvent
        logger.info("Cue '%s' started (triggered by %s)", cue.id, event.event_type)
        self.active_cue = cue.id
        self.total_steps = len(cue.actions)
        self.active_step = 0
        self.active_label = ""
        await self._event_bus.publish(CueStartedEvent(cue_id=cue.id, source="engine"))
        try:
            for i, action in enumerate(cue.actions):
                self.active_step = i + 1
                self.active_label = self._action_label(action)
                await self._execute_action(action, event)
            await self._event_bus.publish(CueCompletedEvent(cue_id=cue.id, source="engine"))
        except asyncio.CancelledError:
            logger.info("Cue '%s' cancelled", cue.id)
            await self._event_bus.publish(CueCancelledEvent(cue_id=cue.id, reason="cancelled", source="engine"))
        except Exception as e:
            logger.error("Cue '%s' error: %s", cue.id, e)
        finally:
            self.active_cue = None
            self.active_step = 0
            self.total_steps = 0
            self.active_label = ""

    def _load_groups(self, groups) -> None:
        self._groups = {g.id: list(g.fixture_ids) for g in groups}
        logger.info("Loaded %d fixture groups", len(self._groups))

    def reload_groups(self, groups) -> None:
        """Hot-reload fixture group assignments."""
        self._load_groups(groups)

    def reload_cues(self, cues_data: list[dict]) -> None:
        """Replace all loaded cues in place (hot reload — no restart needed)."""
        self._cues = []
        self._load_cues(cues_data)
        logger.info("Cues hot-reloaded: %d loaded", len(self._cues))

    def _action_label(self, action: ActionDef) -> str:
        t = action.type
        p = action.params
        labels = {
            "set_dmx_scene":  lambda: f"DMX → {p.get('scene')}",
            "fade_dmx_scene": lambda: f"Fade → {p.get('scene')} ({p.get('duration_ms')}ms)",
            "dmx_flash":      lambda: f"Flash {p.get('scene')} ×{p.get('count', 3)}",
            "wait":           lambda: f"Wait {p.get('duration_ms')}ms",
            "blackout":       lambda: "All Off",
            "set_relay":      lambda: f"Relay {p.get('relay')} → {p.get('state')}",
            "pixel_scene":    lambda: f"Pixels fill {p.get('color')}",
            "pixel_chase":    lambda: f"Pixel chase {p.get('duration_ms')}ms",
            "pixel_off":      lambda: "Pixels off",
            "parallel":       lambda: f"Parallel ({len(p.get('actions', []))} tracks)",
            "group_color":    lambda: f"Group {p.get('group')} → solid",
            "group_flash":    lambda: f"Group {p.get('group')} flash ×{p.get('count', 3)}",
            "group_chase":    lambda: f"Group {p.get('group')} chase {p.get('duration_ms')}ms",
            "set_fixture":    lambda: f"Fixture {p.get('fixture') or p.get('group')} → {list(p.get('channels', {}).keys())}",
            "group_effect":   lambda: f"Group {p.get('group')} {p.get('effect', 'flash')}",
        }
        fn = labels.get(t)
        return fn() if fn else t

    async def _execute_action(self, action: ActionDef, event) -> None:
        t = action.type
        p = action.params

        if t == "set_dmx_scene":
            self._scene_manager.apply_scene(p["scene"])

        elif t == "fade_dmx_scene":
            await self._scene_manager.fade_to_scene(
                p["scene"], float(p.get("duration_ms", 1000))
            )

        elif t == "dmx_flash":
            # Flash a scene on/off N times then return to a scene
            on_scene = p["scene"]
            return_scene = p.get("return_scene", "blackout")
            count = int(p.get("count", 3))
            on_ms = float(p.get("on_ms", 200))
            off_ms = float(p.get("off_ms", 200))
            for _ in range(count):
                self._scene_manager.apply_scene(on_scene)
                await asyncio.sleep(on_ms / 1000)
                self._scene_manager.apply_scene(return_scene)
                await asyncio.sleep(off_ms / 1000)

        elif t == "wait":
            await asyncio.sleep(float(p.get("duration_ms", 0)) / 1000)

        elif t == "blackout":
            self._scene_manager.blackout_all()

        elif t == "set_relay":
            if self._relay_manager is None:
                logger.warning("set_relay action: no relay manager configured")
                return
            relay_id = p["relay"]
            state = bool(p.get("state", False))
            if isinstance(p.get("state"), str):
                state = p["state"].lower() in ("on", "true", "1", "yes")
            from parade.core.state import SystemState
            if (
                state
                and self._state_machine is not None
                and self._state_machine.state != SystemState.RUNNING
            ):
                # Turning a relay off is always allowed; on only while RUNNING.
                logger.warning(
                    "set_relay %s ON refused: state is %s", relay_id, self._state_machine.state.value
                )
                return
            await self._relay_manager.set_relay(relay_id, state)

        elif t == "pixel_scene":
            if self._pixel_manager is None:
                logger.warning("pixel_scene action: no pixel manager configured")
                return
            color = p.get("color", [0, 0, 0])
            await self._pixel_manager.set_all(*color)
            await self._pixel_manager.show()

        elif t == "pixel_chase":
            if self._pixel_manager is None:
                logger.warning("pixel_chase action: no pixel manager configured")
                return
            await self._run_pixel_chase(p)

        elif t == "pixel_off":
            if self._pixel_manager is None:
                return
            await self._pixel_manager.set_all(0, 0, 0)
            await self._pixel_manager.show()

        elif t == "parallel":
            raw_subs = p.get("actions", [])
            sub_pairs = [
                (
                    ActionDef(type=a["type"], params={k: v for k, v in a.items() if k not in ("type", "delay_ms")}),
                    float(a.get("delay_ms", 0)),
                )
                for a in raw_subs
            ]

            async def _run_delayed(sa, delay, ev=event):
                if delay > 0:
                    await asyncio.sleep(delay / 1000)
                await self._execute_action(sa, ev)

            if sub_pairs:
                await asyncio.gather(*[_run_delayed(sa, d) for sa, d in sub_pairs])

        elif t == "group_color":
            color = p.get("color", [255, 255, 255])
            for fid in self._groups.get(p.get("group", ""), []):
                self._scene_manager.set_fixture_rgb(fid, *color)

        elif t == "group_flash":
            fixture_ids = self._groups.get(p.get("group", ""), [])
            colors = p.get("colors", [[255, 255, 255]])
            count = int(p.get("count", 3))
            on_ms = float(p.get("on_ms", 200))
            off_ms = float(p.get("off_ms", 200))
            for i in range(count):
                color = colors[i % len(colors)]
                for fid in fixture_ids:
                    self._scene_manager.set_fixture_rgb(fid, *color)
                await asyncio.sleep(on_ms / 1000)
                for fid in fixture_ids:
                    self._scene_manager.set_fixture_off(fid)
                await asyncio.sleep(off_ms / 1000)

        elif t == "group_chase":
            fixture_ids = self._groups.get(p.get("group", ""), [])
            color = p.get("color", [255, 255, 255])
            duration_ms = float(p.get("duration_ms", 2000))
            speed_ms = float(p.get("speed_ms", 100))
            if fixture_ids:
                loop = asyncio.get_event_loop()
                end_time = loop.time() + duration_ms / 1000
                pos = 0
                while loop.time() < end_time:
                    for i, fid in enumerate(fixture_ids):
                        if i == pos % len(fixture_ids):
                            self._scene_manager.set_fixture_rgb(fid, *color)
                        else:
                            self._scene_manager.set_fixture_off(fid)
                    pos += 1
                    await asyncio.sleep(speed_ms / 1000)
                for fid in fixture_ids:
                    self._scene_manager.set_fixture_off(fid)

        elif t == "set_fixture":
            fixture_id = p.get("fixture") or p.get("fixture_id")
            group_id = p.get("group") or p.get("group_id")
            channels = {k: int(v) for k, v in p.get("channels", {}).items()}
            fade_ms = float(p.get("fade_ms", 0))
            if group_id:
                fids = self._groups.get(group_id, [])
            elif fixture_id:
                fids = [fixture_id]
            else:
                fids = []
            for fid in fids:
                self._scene_manager.set_fixture_channels(fid, channels, fade_ms)

        elif t == "group_effect":
            effect = p.get("effect", "flash")
            group = p.get("group", "")
            fixture_ids = self._groups.get(group, [])
            if effect == "solid":
                color = p.get("color", [255, 255, 255])
                for fid in fixture_ids:
                    self._scene_manager.set_fixture_rgb(fid, *color)
            elif effect == "flash":
                colors = p.get("colors", [[255, 255, 255]])
                count = int(p.get("count", 15))
                on_ms = float(p.get("on_ms", 200))
                off_ms = float(p.get("off_ms", 200))
                for i in range(count):
                    color = colors[i % len(colors)]
                    for fid in fixture_ids:
                        self._scene_manager.set_fixture_rgb(fid, *color)
                    await asyncio.sleep(on_ms / 1000)
                    for fid in fixture_ids:
                        self._scene_manager.set_fixture_off(fid)
                    await asyncio.sleep(off_ms / 1000)
            elif effect == "chase":
                color = p.get("color", [255, 255, 255])
                duration_ms = float(p.get("duration_ms", 5000))
                speed_ms = float(p.get("speed_ms", 100))
                if fixture_ids:
                    loop = asyncio.get_event_loop()
                    end_time = loop.time() + duration_ms / 1000
                    pos = 0
                    while loop.time() < end_time:
                        for i, fid in enumerate(fixture_ids):
                            if i == pos % len(fixture_ids):
                                self._scene_manager.set_fixture_rgb(fid, *color)
                            else:
                                self._scene_manager.set_fixture_off(fid)
                        pos += 1
                        await asyncio.sleep(speed_ms / 1000)
                    for fid in fixture_ids:
                        self._scene_manager.set_fixture_off(fid)

        elif t == "set_var":
            name = p.get("name", "")
            value = p.get("value", True)
            if name:
                self._vars[name] = value
                logger.debug("Engine var set: %s = %r", name, value)

        else:
            logger.warning("Unknown action type: %s", t)

    async def _run_pixel_chase(self, p: dict) -> None:
        color = tuple(p.get("color", [255, 255, 255]))
        background = tuple(p.get("background", [0, 0, 0]))
        duration_ms = float(p.get("duration_ms", 2000))
        speed_ms = float(p.get("speed_ms", 50))
        count = self._pixel_manager.get_pixel_count()

        loop = asyncio.get_event_loop()
        end_time = loop.time() + duration_ms / 1000
        pos = 0

        while loop.time() < end_time:
            await self._pixel_manager.set_all(*background)
            await self._pixel_manager.set_pixel(pos % count, *color)
            await self._pixel_manager.show()
            pos += 1
            await asyncio.sleep(speed_ms / 1000)

        await self._pixel_manager.set_all(*background)
        await self._pixel_manager.show()
