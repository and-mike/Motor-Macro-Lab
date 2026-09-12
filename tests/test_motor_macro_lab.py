import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from motor_macro_lab import MidiMacroEvolutionLab


class MidiMacroEvolutionLabTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lab = MidiMacroEvolutionLab(ppq=480)

    def test_translates_keypress_knob_and_automation(self) -> None:
        result = self.lab.translate(
            {
                "events": [
                    {"type": "keypress", "note": 60, "velocity": 110, "duration": 120},
                    {"type": "knob_assignment", "parameter": "filter_cutoff", "value": 88},
                    {"type": "automation", "parameter": "envelope_attack", "start": 10, "end": 20, "steps": 2, "duration": 60},
                ]
            }
        )

        event_types = [event["type"] for event in result["timeline"]]
        self.assertIn("note_on", event_types)
        self.assertIn("note_off", event_types)

        cutoff_events = [event for event in result["timeline"] if event.get("parameter") == "filter_cutoff"]
        self.assertEqual(cutoff_events[0]["cc"], 74)
        self.assertEqual(cutoff_events[0]["value"], 88)

        attack_events = [event for event in result["timeline"] if event.get("parameter") == "envelope_attack"]
        self.assertEqual(len(attack_events), 3)
        self.assertEqual([event["value"] for event in attack_events], [10, 15, 20])
        self.assertEqual(next(event for event in result["timeline"] if event["type"] == "note_on")["channel"], 0)

    def test_loop_bank_macro_and_conditional(self) -> None:
        spec = {
            "context": {"mode": "lead"},
            "macros": {
                "A": {
                    "riff": [
                        {"type": "keypress", "note": 64, "duration": 60},
                        {"type": "keypress", "note": 67, "duration": 60},
                    ]
                }
            },
            "events": [
                {"type": "loop", "count": 2, "events": [{"type": "bank_macro", "bank": "A", "macro": "riff"}]},
                {
                    "type": "conditional",
                    "if": {"var": "mode", "equals": "lead"},
                    "then": [{"type": "keypress", "note": 72, "duration": 30}],
                    "else": [{"type": "keypress", "note": 55, "duration": 30}],
                },
            ],
        }

        result = self.lab.translate(spec)
        note_ons = [event for event in result["timeline"] if event["type"] == "note_on"]
        played_notes = [event["note"] for event in note_ons]

        self.assertEqual(played_notes.count(64), 2)
        self.assertEqual(played_notes.count(67), 2)
        self.assertIn(72, played_notes)
        self.assertNotIn(55, played_notes)

    def test_automation_ticks_use_integer_interpolation(self) -> None:
        result = self.lab.translate(
            {
                "events": [
                    {"type": "automation", "parameter": "filter_cutoff", "start": 0, "end": 100, "steps": 4, "duration": 5}
                ]
            }
        )
        ticks = [event["tick"] for event in result["timeline"] if event["type"] == "control_change"]
        self.assertEqual(ticks, [0, 1, 2, 3, 5])

    def test_automation_steps_greater_than_duration_are_clamped(self) -> None:
        result = self.lab.translate(
            {
                "events": [
                    {"type": "automation", "parameter": "filter_cutoff", "start": 0, "end": 127, "steps": 8, "duration": 3}
                ]
            }
        )
        ticks = [event["tick"] for event in result["timeline"] if event["type"] == "control_change"]
        self.assertEqual(ticks, [0, 1, 2, 3])

    def test_arpeggio_effect_and_generative_task(self) -> None:
        result = self.lab.translate(
            {
                "events": [
                    {"type": "arpeggiator", "notes": [60, 64, 67], "pattern": "updown", "repeats": 1, "step_ticks": 30},
                    {"type": "effect_event", "effect": "chorus", "value": 99},
                    {
                        "type": "preset_generative_task",
                        "task": "chord_progression",
                        "seed": 3,
                        "length": 2,
                        "root": 57,
                        "velocity": 77,
                        "channel": 2,
                    },
                ]
            }
        )

        note_ons = [event for event in result["timeline"] if event["type"] == "note_on"]
        self.assertGreaterEqual(len(note_ons), 5)
        arp_note_off_ticks = [
            event["tick"]
            for event in result["timeline"]
            if event["type"] == "note_off" and event["tick"] <= 120
        ]
        self.assertIn(29, arp_note_off_ticks)

        chorus_events = [event for event in result["timeline"] if event.get("parameter") == "chorus"]
        self.assertEqual(chorus_events[0]["cc"], 93)
        self.assertEqual(chorus_events[0]["value"], 99)
        generated_note_ons = [event for event in note_ons if event["tick"] >= 120]
        self.assertTrue(all(event["velocity"] == 77 and event["channel"] == 2 for event in generated_note_ons))

    def test_simultaneous_note_order_is_note_off_before_note_on(self) -> None:
        result = self.lab.translate(
            {
                "events": [
                    {"type": "keypress", "note": 60, "duration": 30},
                    {"type": "keypress", "note": 60, "duration": 30},
                ]
            }
        )

        at_tick_30 = [event for event in result["timeline"] if event["tick"] == 30]
        self.assertEqual([event["type"] for event in at_tick_30[:2]], ["note_off", "note_on"])

    def test_keypress_supports_explicit_nonzero_channel(self) -> None:
        result = self.lab.translate({"events": [{"type": "keypress", "note": 65, "duration": 40, "channel": 4}]})
        on_event = next(event for event in result["timeline"] if event["type"] == "note_on")
        off_event = next(event for event in result["timeline"] if event["type"] == "note_off")
        self.assertEqual(on_event["channel"], 4)
        self.assertEqual(off_event["channel"], 4)

    def test_sequence_absolute_ticks_are_relative_to_sequence_origin(self) -> None:
        result = self.lab.translate(
            {
                "events": [
                    {"type": "keypress", "note": 48, "duration": 50},
                    {
                        "type": "sequence",
                        "events": [
                            {"type": "knob_assignment", "tick": 20, "parameter": "filter_cutoff", "value": 90},
                            {"type": "keypress", "note": 64, "duration": 10},
                        ],
                    },
                ]
            }
        )
        cutoff_event = next(event for event in result["timeline"] if event.get("parameter") == "filter_cutoff")
        sequence_note_on = next(
            event
            for event in result["timeline"]
            if event["type"] == "note_on" and event["note"] == 64
        )
        self.assertEqual(cutoff_event["tick"], 70)
        self.assertEqual(sequence_note_on["tick"], 70)

    def test_cli_writes_translated_output_file(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        cli_path = repo_root / "motor_macro_lab.py"
        spec = {"events": [{"type": "keypress", "note": 60, "duration": 10}]}

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.json"
            output_path = Path(temp_dir) / "output.json"
            input_path.write_text(json.dumps(spec), encoding="utf-8")

            subprocess.run(
                [sys.executable, str(cli_path), "--input", str(input_path), "--output", str(output_path)],
                check=True,
                cwd=repo_root,
            )

            translated = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertIn("timeline", translated)
            self.assertEqual(translated["timeline"][0]["type"], "note_on")


if __name__ == "__main__":
    unittest.main()
