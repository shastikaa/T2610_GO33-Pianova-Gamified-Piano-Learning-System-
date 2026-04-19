# T2610_GO33-Pianova-Gamified-Piano-Learning-System-

## Why it may not work on another laptop

This project includes local virtual environment folders such as `venv/` and `.venv/`.
Those folders are machine-specific and contain references to the Python installation on the computer where they were created, so they should not be copied and reused on a different laptop.

This app also depends on Python packages that must be installed on the other machine.

## Run on another laptop

1. Install Python 3.11 or newer.
2. Open the project folder in a terminal.
3. Create a fresh virtual environment:

```powershell
py -m venv .venv
```

4. Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

5. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

6. Start the app:

```powershell
python app.py
```

7. Open this address in the browser on the same laptop:

```text
http://127.0.0.1:5000
```

## If you want another laptop on the same Wi-Fi to open it

The Flask development server only listens on the current computer by default.
If you want your friend to open the app from a different laptop on the same network, run Flask so it listens on all interfaces:

```powershell
flask --app app run --host=0.0.0.0 --port=5000
```

Then open `http://YOUR-IP-ADDRESS:5000` on the other laptop.