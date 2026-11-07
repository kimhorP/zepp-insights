<h1 align="center">zepp-insights</h1>

![Python](https://img.shields.io/badge/python-3.12-3776ab?logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-0f80cc?logo=sqlite&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-2.2.3-150000?logo=pandas&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.2-000000?logo=flask&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-2c6e91?logo=ollama&logoColor=white)
![Pydantic](https://img.shields.io/badge/pydantic-v2-e9218a?logo=pydantic&logoColor=white)

zepp-insights extracts health insights from your Amazfit watch with the help of AI. Your watch collects the data — zepp-insights pulls it into a local database, shows what it means, and lets an AI interpret it for you. Explore trends, recovery, and training load in a dashboard built on your machine, where your health data belongs to you.

## Data Types

| Type | Description |
|------|-------------|
| `heart-rate` | Minute-by-minute BPM readings |
| `sleep` | Nightly score, stages (light/deep/REM/awake), duration, resting HR |
| `steps` | Daily total, distance, calories, activity segments |
| `stress` | 5-minute interval stress levels with zone percentages |
| `training-load` | ATL, CTL, TSB, exercise score |
| `sport-load` | Daily and weekly training load with optimal range |
| `phn` | TRIMP (Training Impulse) and derived ATL/CTL/TSB |


---

*This project is not affiliated with Zepp Health, Huami, or Amazfit.*