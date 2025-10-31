# SaaS Security Monitoring Agent & Dashboard

This project is a solution for the Software Engineer assignment. It consists of a Python-based Linux agent that collects system information and a Python FastAPI backend with a simple web frontend to display the data.

## Project Structure

```
saas_project/
├── agent/              # The data collection agent
│   ├── agent.py
│   ├── requirements.txt
│   └── packaging/      # Files for building the .deb package
├── backend/            # The FastAPI server and web dashboard
│   ├── main.py
│   ├── requirements.txt
│   └── templates/      # HTML templates for the frontend
└── README.md           # This file
```

---

## How to Run the Application

You will need two terminal windows to run the backend server and the agent simultaneously.

**Prerequisites:**

- Python 3.7+
- `venv` for creating virtual environments
- `dpkg-deb` for packaging (available on Debian/Ubuntu)

### Terminal 1: Start the Backend Server

The backend server receives data from the agent and displays it on the web dashboard.

```bash
# 1. Navigate to the backend directory
cd saas_project/backend

# 2. Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install the required dependencies
pip install -r requirements.txt

# 4. Run the FastAPI server
# The --reload flag automatically restarts the server on code changes.
uvicorn main:app --reload
```

Once running, the server will be available at `http://127.0.0.1:8000`.

### Terminal 2: Run the Agent

The agent collects data from the machine it's running on and sends it to the backend.

```bash
# 1. Navigate to the agent directory
cd saas_project/agent

# 2. Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install the required dependencies
pip install -r requirements.txt

# 4. Run the agent script
# sudo is required because many security checks need root privileges to inspect system files.
sudo python3 agent.py
```

After the agent runs, it will print the collected JSON data to the console and send it to the backend server.

### View the Results

1.  Open your web browser and navigate to `http://127.0.0.1:8000`.
2.  You will see the hostname of the machine where you ran the agent.
3.  Click the hostname to view the detailed report, including host information, CIS check results, and a list of all installed packages.

---

## How to Package the Agent

The assignment requires the agent to be in a proper package format (`.deb` for Ubuntu/Debian).

```bash
# 1. Navigate to the agent directory
cd saas_project/agent

# 2. Run the dpkg-deb command to build the package
# This command takes the 'debian' directory and packages it into a .deb file.
dpkg-deb --build packaging/debian
```

After running the command, you will find the package `debian.deb` in the `saas_project/agent/packaging/` directory. You can rename it to `saas-security-agent_1.0.0_all.deb` for clarity.

**To install the package (for testing):**

```bash
sudo dpkg -i saas_project/agent/packaging/debian.deb
```

**After installation, the agent will be available at `/usr/local/bin/saas-agent`.**
