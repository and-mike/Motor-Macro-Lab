from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from typing import Any


CC_MAP = {
    "modulation": 1,
    "envelope_attack": 73,
    "envelope_decay": 75,
    "envelope_sustain": 70,
    "envelope_release": 72,
    "filter_cutoff": 74,
    "filter_resonance": 71,
    "pso_shape": 79,
    "effect_mix": 91,
}

EFFECT_CC_MAP = {
    "reverb": 91,
    "chorus": 93,
    "delay": 94,
}


@dataclass
class MidiMacroEvolutionLab:
    ppq: int = 480

    def translate(self, spec: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        effective_context = dict(spec.get("context", {}))
        if context:
            effective_context.update(context)

        events, total_ticks = self._compile_actions(
            actions=spec.get("events", []),
            macros=spec.get("macros", {}),
            context=effective_context,
            tick=0,
        )

        event_order = {
            "note_off": 10,
            "control_change": 20,
            "note_on": 30,
            "meta": 40,
        }
        timeline = sorted(events, key=lambda event: (event["tick"], event_order.get(event["type"], 50)))
        return {
            "ppq": int(spec.get("ppq", self.ppq)),
            "tempo": int(spec.get("tempo", 120)),
            "total_ticks": total_ticks,
            "timeline": timeline,
        }

    def _compile_actions(
        self,
        actions: list[dict[str, Any]],
        macros: dict[str, Any],
        context: dict[str, Any],
        tick: int,
    ) -> tuple[list[dict[str, Any]], int]:
        cursor = tick
        compiled: list[dict[str, Any]] = []

        for action in actions:
            action_tick = int(action.get("tick", cursor + int(action.get("offset", 0))))
            action_events, consumed = self._compile_action(action, macros, context, action_tick)
            compiled.extend(action_events)
            cursor = max(cursor, action_tick + consumed)

        return compiled, cursor - tick

    def _compile_action(
        self,
        action: dict[str, Any],
        macros: dict[str, Any],
        context: dict[str, Any],
        tick: int,
    ) -> tuple[list[dict[str, Any]], int]:
        action_type = action.get("type")

        if action_type == "keypress":
            return self._compile_keypress(action, tick)
        if action_type == "chord":
            return self._compile_chord(action, tick)
        if action_type in {"arpeggio", "arpeggiator", "arpeggios"}:
            return self._compile_arpeggio(action, tick)
        if action_type in {"knob_assignment", "modulation"}:
            return self._compile_knob(action, tick)
        if action_type == "automation":
            return self._compile_automation(action, tick)
        if action_type == "sequence":
            return self._compile_sequence(action, macros, context, tick)
        if action_type == "phrase":
            return self._compile_sequence(action, macros, context, tick)
        if action_type == "loop":
            return self._compile_loop(action, macros, context, tick)
        if action_type == "conditional":
            return self._compile_conditional(action, macros, context, tick)
        if action_type == "bank_macro":
            return self._compile_bank_macro(action, macros, context, tick)
        if action_type in {"effect_event", "effect"}:
            return self._compile_effect(action, tick)
        if action_type in {"preset_generative_task", "generative_task"}:
            return self._compile_generative(action, tick)

        return ([{"tick": tick, "type": "meta", "name": "unknown_action", "action": action}], 0)

    def _compile_keypress(self, action: dict[str, Any], tick: int) -> tuple[list[dict[str, Any]], int]:
        note = int(action.get("note", 60))
        velocity = int(action.get("velocity", 100))
        duration = max(1, int(action.get("duration", self.ppq // 4)))
        channel = int(action.get("channel", 0))
        return (
            [
                {"tick": tick, "type": "note_on", "note": note, "velocity": velocity, "channel": channel},
                {"tick": tick + duration, "type": "note_off", "note": note, "velocity": 0, "channel": channel},
            ],
            duration,
        )

    def _compile_chord(self, action: dict[str, Any], tick: int) -> tuple[list[dict[str, Any]], int]:
        notes = [int(note) for note in action.get("notes", [60, 64, 67])]
        velocity = int(action.get("velocity", 100))
        duration = max(1, int(action.get("duration", self.ppq // 2)))
        channel = int(action.get("channel", 0))
        events = []
        for note in notes:
            events.append({"tick": tick, "type": "note_on", "note": note, "velocity": velocity, "channel": channel})
            events.append({"tick": tick + duration, "type": "note_off", "note": note, "velocity": 0, "channel": channel})
        return events, duration

    def _compile_arpeggio(self, action: dict[str, Any], tick: int) -> tuple[list[dict[str, Any]], int]:
        notes = [int(note) for note in action.get("notes", [60, 64, 67, 72])]
        pattern = action.get("pattern", "up")
        repeats = max(1, int(action.get("repeats", 1)))
        step_ticks = max(1, int(action.get("step_ticks", self.ppq // 8)))
        gate_ticks = max(1, int(action.get("gate_ticks", step_ticks)))
        velocity = int(action.get("velocity", 96))
        channel = int(action.get("channel", 0))

        if pattern == "down":
            ordered_notes = list(reversed(notes))
        elif pattern == "updown":
            ordered_notes = notes + notes[-2:0:-1] if len(notes) > 2 else notes
        elif pattern == "random":
            rnd = random.Random(int(action.get("seed", 61)))
            ordered_notes = notes[:]
            rnd.shuffle(ordered_notes)
        else:
            ordered_notes = notes

        events = []
        position = tick
        for _ in range(repeats):
            for note in ordered_notes:
                events.append({"tick": position, "type": "note_on", "note": note, "velocity": velocity, "channel": channel})
                events.append(
                    {
                        "tick": position + gate_ticks,
                        "type": "note_off",
                        "note": note,
                        "velocity": 0,
                        "channel": channel,
                    }
                )
                position += step_ticks

        return events, position - tick

    def _compile_knob(self, action: dict[str, Any], tick: int) -> tuple[list[dict[str, Any]], int]:
        parameter = action.get("parameter", "filter_cutoff")
        cc = int(action.get("cc", CC_MAP.get(parameter, 74)))
        value = max(0, min(127, int(action.get("value", 64))))
        channel = int(action.get("channel", 0))
        return (
            [
                {
                    "tick": tick,
                    "type": "control_change",
                    "cc": cc,
                    "value": value,
                    "channel": channel,
                    "parameter": parameter,
                }
            ],
            0,
        )

    def _compile_automation(self, action: dict[str, Any], tick: int) -> tuple[list[dict[str, Any]], int]:
        parameter = action.get("parameter", "filter_cutoff")
        cc = int(action.get("cc", CC_MAP.get(parameter, 74)))
        start = int(action.get("start", 0))
        end = int(action.get("end", 127))
        steps = max(1, int(action.get("steps", 8)))
        duration = max(1, int(action.get("duration", self.ppq)))
        channel = int(action.get("channel", 0))
        step_size = duration / steps
        events = []

        for index in range(steps + 1):
            fraction = index / steps
            value = int(round(start + (end - start) * fraction))
            events.append(
                {
                    "tick": int(tick + round(step_size * index)),
                    "type": "control_change",
                    "cc": cc,
                    "value": max(0, min(127, value)),
                    "channel": channel,
                    "parameter": parameter,
                }
            )

        return events, duration

    def _compile_sequence(
        self,
        action: dict[str, Any],
        macros: dict[str, Any],
        context: dict[str, Any],
        tick: int,
    ) -> tuple[list[dict[str, Any]], int]:
        steps = action.get("steps", action.get("events", []))
        normalized_steps = []
        for step in steps:
            if isinstance(step, int):
                normalized_steps.append({"type": "keypress", "note": step})
            else:
                normalized_steps.append(step)
        return self._compile_actions(normalized_steps, macros, context, tick)

    def _compile_loop(
        self,
        action: dict[str, Any],
        macros: dict[str, Any],
        context: dict[str, Any],
        tick: int,
    ) -> tuple[list[dict[str, Any]], int]:
        count = max(0, int(action.get("count", 1)))
        body = action.get("events", [])
        all_events: list[dict[str, Any]] = []
        cursor = tick

        for _ in range(count):
            events, consumed = self._compile_actions(body, macros, context, cursor)
            all_events.extend(events)
            cursor += consumed

        return all_events, cursor - tick

    def _compile_conditional(
        self,
        action: dict[str, Any],
        macros: dict[str, Any],
        context: dict[str, Any],
        tick: int,
    ) -> tuple[list[dict[str, Any]], int]:
        condition = action.get("if", {})
        key = condition.get("var")
        expected = condition.get("equals")
        actual = context.get(key)

        branch = action.get("then", []) if actual == expected else action.get("else", [])
        return self._compile_actions(branch, macros, context, tick)

    def _compile_bank_macro(
        self,
        action: dict[str, Any],
        macros: dict[str, Any],
        context: dict[str, Any],
        tick: int,
    ) -> tuple[list[dict[str, Any]], int]:
        bank = str(action.get("bank", "A"))
        macro_name = str(action.get("macro", "default"))

        selected = None
        if isinstance(macros.get(bank), dict):
            selected = macros[bank].get(macro_name)
        if selected is None:
            selected = macros.get(f"{bank}:{macro_name}", macros.get(macro_name, []))

        if not isinstance(selected, list):
            selected = []

        return self._compile_actions(selected, macros, context, tick)

    def _compile_effect(self, action: dict[str, Any], tick: int) -> tuple[list[dict[str, Any]], int]:
        effect = str(action.get("effect", "reverb"))
        value = max(0, min(127, int(action.get("value", 64))))
        channel = int(action.get("channel", 0))
        cc = EFFECT_CC_MAP.get(effect)

        if cc is not None:
            return (
                [
                    {
                        "tick": tick,
                        "type": "control_change",
                        "cc": cc,
                        "value": value,
                        "channel": channel,
                        "parameter": effect,
                    }
                ],
                0,
            )

        return ([{"tick": tick, "type": "meta", "name": "effect_event", "effect": effect, "value": value}], 0)

    def _compile_generative(self, action: dict[str, Any], tick: int) -> tuple[list[dict[str, Any]], int]:
        task_name = str(action.get("task", "chord_progression"))
        seed = int(action.get("seed", 61))
        length = max(1, int(action.get("length", 4)))
        root = int(action.get("root", 60))
        bar_ticks = max(1, int(action.get("bar_ticks", self.ppq)))

        if task_name != "chord_progression":
            return ([{"tick": tick, "type": "meta", "name": "unknown_generative_task", "task": task_name}], 0)

        rnd = random.Random(seed)
        major_intervals = [0, 4, 7]
        minor_intervals = [0, 3, 7]
        chord_offsets = [0, 5, 7, 9]

        events: list[dict[str, Any]] = []
        cursor = tick
        for _ in range(length):
            offset = rnd.choice(chord_offsets)
            shape = rnd.choice([major_intervals, minor_intervals])
            notes = [root + offset + interval for interval in shape]
            chord_events, _ = self._compile_chord({"notes": notes, "duration": bar_ticks, "velocity": 90}, cursor)
            events.extend(chord_events)
            cursor += bar_ticks

        return events, cursor - tick


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate Motor 61 macro specs into MIDI-style timelines.")
    parser.add_argument("--input", required=True, help="Path to input JSON spec")
    parser.add_argument("--output", help="Path for translated output JSON; defaults to stdout")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as source_file:
        spec = json.load(source_file)

    result = MidiMacroEvolutionLab().translate(spec)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as output_file:
            json.dump(result, output_file, indent=2)
            output_file.write("\n")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
