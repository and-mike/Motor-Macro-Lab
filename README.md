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
- preset generative tasks (currently deterministic chord progression generation)

## Usage

```bash
python /home/runner/work/Motor-Macro-Lab/Motor-Macro-Lab/motor_macro_lab.py --input /path/to/spec.json
```

Optional output file:

```bash
python /home/runner/work/Motor-Macro-Lab/Motor-Macro-Lab/motor_macro_lab.py --input /path/to/spec.json --output /path/to/result.json
```

## Testing

```bash
cd /home/runner/work/Motor-Macro-Lab/Motor-Macro-Lab
python -m unittest discover -s tests
```
