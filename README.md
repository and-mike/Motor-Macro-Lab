# Motor-Macro-Lab

MIDI Macro Evolution Lab for Behringer Motor 61 keyboards.

This project now includes a lightweight translator that converts high-level macro specs into a MIDI-style event timeline.

## Supported macro/event concepts

- keypresses, velocity, modulation controls
- bank macros
- knob assignment to envelope, filter, and PSO-style parameters
- automation envelopes
- loops and conditional statements
- chords, arpeggiators/arpeggios
- sequences and phrases
- effect events (reverb/chorus/delay)
- preset generative tasks (currently seed-based reproducible chord progression generation)

## Usage

```bash
python motor_macro_lab.py --input /path/to/spec.json
```

Optional output file:

```bash
python motor_macro_lab.py --input /path/to/spec.json --output /path/to/result.json
```

Python API:

```python
from motor_macro_lab import MidiMacroEvolutionLab

spec = {"events": [{"type": "keypress", "note": 60, "duration": 120}]}
timeline = MidiMacroEvolutionLab().translate(spec)
```

## Testing

```bash
python -m unittest discover -s tests
```
