# Deployment (Render)

The repo is Render-ready as-is:

1. On [render.com](https://render.com), **New > Blueprint**, point it at this repo — `render.yaml` configures the Python version, the build (`pip install -r requirements.txt`) and the start command.
2. Or create a **New > Web Service** manually (Python 3.12+, free plan is fine) with build command `pip install -r requirements.txt` and start command:

   ```bash
   gunicorn app.app:server --bind 0.0.0.0:$PORT --worker-class gthread --workers 1 --threads 4 --timeout 120
   ```

**Python version.** `render.yaml` sets `PYTHON_VERSION` to a full version (3.14.8). Render needs the full version number, and the environment variable wins over a `.python-version` file. The supported floor for running the code locally is 3.12, because numpy 2.5 dropped 3.11.

**Why a threaded worker.** Dash fires every tab's callbacks as simultaneous requests on page load. With gunicorn's default single sync worker those requests queue one at a time, and on Render's free tier a slow one could wait long enough to hit the 30-second default timeout, surfacing as intermittent `502`s and a blank tab. Threads share the already-loaded data inside one process (unlike extra worker processes, which would each duplicate it).

**Gotcha.** For a service created manually, the Start Command lives in Render's dashboard settings: editing `Procfile` or `render.yaml` later does *not* change an existing service. Update it under **Settings > Start Command**.

**Health and debug endpoints.** `/healthz` answers 200 with `{"status": "ok"}` once the data has loaded; `render.yaml` sets it as the health check path (for a service created manually, set it under **Settings > Health Check Path**). `/debugz` returns the process's uptime, Python and package versions, the rows loaded and its resident memory in MB (read from `/proc` on Linux, so it is blank on Windows). It carries no settings or paths.

**No secrets needed.** The dashboard reads only the processed CSVs committed under `data/processed/`. The raw BLS archives are git-ignored (see [.gitignore](../.gitignore)): Render can't reliably regenerate the processed tables at build time, since BLS's API has had multi-day outages.

`app/app.py`'s `if __name__ == "__main__"` block is for local development (`python app/app.py`; reads `PORT` and `DASH_DEBUG`, defaults to port 8051 with debug on). In production, gunicorn serves `app.app:server`.
