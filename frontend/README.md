# Tianheng Streamlit MVP

Run from the repository root:

```bash
python -m streamlit run app.py
```

The default **offline demo mode** uses deterministic synthetic weather and
radar data. Turn it off only when authorised live-source environment variables
are configured. Every source is labelled `LIVE`, `CACHED`, `SYNTHETIC`, or
`UNAVAILABLE` in the UI.

The current backend is a point-based research service. This MVP therefore does
not claim to be a city-wide risk grid, an official warning publisher, or a
production 30/60/120-minute forecast system. Official warnings must remain a
separate, human-reviewed workflow.
