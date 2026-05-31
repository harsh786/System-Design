# AI Risk Register Tool

Interactive tool for managing an AI risk register — catalog risks, score them, assign owners, and generate reports.

## Features
- Pre-populated with 10 common AI risks
- Add new risks interactively
- Score risks using likelihood × impact matrix
- Assign owners and controls
- Generate risk reports sorted by severity
- Text-based risk matrix visualization

## Usage

```bash
pip install -r requirements.txt
python main.py
```

## Commands
- `list` — Show all risks sorted by score
- `add` — Add a new risk interactively
- `score <id>` — Re-score a risk
- `control <id>` — Add controls to a risk
- `matrix` — Show risk matrix visualization
- `report` — Generate full risk report
- `help` — Show commands
- `quit` — Exit
