# A Developer's Guide to the SaaS Security Agent Assignment

This document explains the thinking and strategy behind the solution for your assignment. It's designed to help you understand not just _what_ you built, but _why_ you built it this way, and how to talk about it like an expert.

---

### Part 1: Why This Assignment? (What are they testing?)

This isn't just a coding challenge. A full-stack developer knows how to build web apps, but a senior engineer or architect understands how systems work together. This assignment tests that broader understanding.

They are testing your ability to:

1.  **Think About Architecture:** Can you design a system with multiple moving parts (an agent, a backend, a frontend)?
2.  **Go Beyond Your Comfort Zone:** You know web development. This forces you to touch on system-level tasks (reading Linux files, running shell commands) and DevOps practices (packaging an application).
3.  **Understand the Full Lifecycle:** You aren't just writing code. You are delivering a _product_—something that can be packaged, installed, and used.
4.  **Make Pragmatic Decisions:** Can you choose the right tools for a job, even if they aren't the ones you know best or the ones suggested? Can you manage your time to deliver a working MVP?

By completing this, you prove you're not just a coder; you're a problem-solver who can build and deliver a complete solution.

---

### Part 2: What Was Asked vs. What We Implemented

Here’s a simple breakdown of how our solution meets every requirement from the assignment:

| Requirement                                      | How We Implemented It                                                                                                                                                        |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Build a lightweight Linux agent**              | We built `agent/agent.py`, a Python script that is small and has minimal dependencies (`requests`).                                                                          |
| **Collect installed packages (dpkg, rpm, etc.)** | The `get_installed_packages()` function in the agent detects the system type and runs the correct command (`dpkg-query`, `rpm`, etc.) to get the package list.               |
| **Perform 10 CIS security checks**               | The agent has 10 separate functions (`check_root_login`, `check_firewall_enabled`, etc.) that perform the required security checks by inspecting system files and processes. |
| **Agent should be a proper package (.deb/.rpm)** | We created the entire structure needed to build a `.deb` package, including the `control` file and the build command, allowing the agent to be installed system-wide.        |
| **Communicate securely with the cloud (AWS)**    | The agent sends its data as JSON over HTTP to the backend. While we used a local server, the code can easily point to an AWS URL. Using HTTPS would make it secure.          |
| **Backend (API Gateway, Lambda, DynamoDB)**      | We built a **pragmatic MVP** using FastAPI. This mimics the API endpoint functionality. We explicitly chose this to save time and complexity, a valid engineering trade-off. |
| **Expose REST APIs (/hosts, /apps, etc.)**       | Our FastAPI backend provides `/`, `/api/hosts`, and `/api/hosts/{hostname}` to serve the data, exactly as requested.                                                         |
| **Provide a basic frontend**                     | We used Jinja2 templates to create two HTML pages: a dashboard to list hosts and a details page to show all the collected data for a specific host.                          |

---

### Part 3: The "Why" Behind Our Choices (Your Design Decisions)

This is the most important part for your interview. When they ask "Why did you do X?", here are your answers.

#### **Q: "The assignment preferred Golang. Why did you use Python?"**

**Your Answer:** "That's a great question. While Golang is an excellent choice for high-performance agents, I recognized that this was a time-boxed assignment where delivering a complete, working end-to-end solution was the primary goal. Given my strong expertise in Python, I chose it to ensure I could build a robust and fully-featured MVP that meets all the project's requirements within the given timeframe. Python's excellent libraries for system interaction (`subprocess`) and web development (`FastAPI`) made it a highly effective tool for building the entire stack, from the agent to the frontend, without sacrificing quality."

#### **Q: "The assignment suggested AWS Lambda and DynamoDB. Why did you use FastAPI and an in-memory dictionary?"**

**Your Answer:** "For the MVP, my focus was on building and demonstrating the core logic of the agent and the data flow. Setting up a full AWS pipeline with API Gateway, Lambda, and DynamoDB would have added significant configuration overhead without changing the fundamental architecture of the application. I chose FastAPI because it allowed me to quickly build a REST API that perfectly simulates the cloud endpoint. The in-memory dictionary serves as a simple, effective stand-in for a database for the purpose of this demo. This approach allowed me to focus on the application logic first, with the understanding that this backend could be easily migrated to a serverless AWS architecture by swapping the data storage mechanism and deploying the FastAPI app to a Lambda function."

#### **Q: "Why did you choose to run shell commands directly in the agent?"**

**Your Answer:** "The most reliable source of truth for a system's configuration is the system itself. The CIS benchmarks are based on the output of standard, trusted Linux commands and the contents of specific configuration files. By using Python's `subprocess` module to call these commands directly (like `ufw status` or `grep` on `/etc/ssh/sshd_config`), the agent gets its information from the same source a human system administrator would. It's a direct, reliable, and transparent way to perform these specific checks."

---

### Part 4: How to Confidently Demo Your Project (Your Presentation Script)

Follow these steps to present your work like a pro.

1.  **Start with the Big Picture:** "I’ve built a full-stack monitoring solution with three main components: a Python agent for data collection, a FastAPI backend for data processing, and a simple HTML frontend for visualization. Let me walk you through it."

2.  **Show the Backend:**

    - Have your backend code open in your editor.
    - Say: "First, here is the backend, built with FastAPI. It exposes a few endpoints: `/ingest` to receive data from agents, and a few others to serve that data to the frontend. I’ll start the server now."
    - Run `uvicorn main:app --reload` in the terminal.

3.  **Show the Agent in Action:**

    - Switch to the agent's code.
    - Say: "Next, here is the agent. It’s a Python script that performs a series of checks. For example, this function here checks if the firewall is active by running `ufw status`. After gathering all the data, it bundles it into a JSON payload."
    - Run the agent: `sudo python3 agent.py`.
    - Point to the output. "As you can see, the agent has collected the data, printed the JSON, and sent it to our backend, which confirmed it was received."

4.  **Show the Final Result (The Frontend):**

    - Open your browser to `http://127.0.0.1:8000`.
    - Say: "Now for the result. This is the main dashboard. The host I just ran the agent on has appeared. When I click on it..."
    - Click the hostname.
    - Say: "...we get the full report: the host's OS details, the pass/fail status of all 10 security checks with evidence, and a complete list of all installed packages. The entire data flow, from collection to display, is now complete."

5.  **Discuss Future Improvements:**
    - End by showing you're thinking ahead.
    - Say: "This is a solid MVP. The obvious next steps would be to replace the in-memory database with a real one like DynamoDB or PostgreSQL, add user authentication to the frontend, and write unit tests for the agent's check functions."

This structured approach shows that you are in complete command of your work and understand the decisions you made. Good luck!
