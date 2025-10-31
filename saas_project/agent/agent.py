
import json
import platform
import subprocess
import socket
import requests
import os

# --- Configuration ---
# In a real-world scenario, this should come from a config file or environment variables.
BACKEND_URL = "http://127.0.0.1:8000/ingest"

# --- 1. Host Details Collection ---
def get_host_details():
    """Gathers basic details about the host machine."""
    return {
        "hostname": socket.gethostname(),
        "os_type": platform.system(),
        "os_version": platform.release(),
    }

# --- 2. Package Collection ---
def get_installed_packages():
    """Detects the distro and lists installed packages."""
    packages = []
    try:
        # Check for dpkg (Debian, Ubuntu)
        if subprocess.run(["which", "dpkg"], capture_output=True, text=True).stdout:
            result = subprocess.run(["dpkg-query", "-W", "-f=${Package}\t${Version}\n"], capture_output=True, text=True, check=True)
            for line in result.stdout.strip().split("\n"):
                if line:
                    name, version = line.split("\t")
                    packages.append({"name": name, "version": version})
        # Check for rpm (RHEL, CentOS, Fedora)
        elif subprocess.run(["which", "rpm"], capture_output=True, text=True).stdout:
            result = subprocess.run(["rpm", "-qa", "--qf", "%{NAME}\t%{VERSION}-%{RELEASE}\n"], capture_output=True, text=True, check=True)
            for line in result.stdout.strip().split("\n"):
                if line:
                    name, version = line.split("\t")
                    packages.append({"name": name, "version": version})
        # Check for apk (Alpine)
        elif subprocess.run(["which", "apk"], capture_output=True, text=True).stdout:
            result = subprocess.run(["apk", "info"], capture_output=True, text=True, check=True)
            for line in result.stdout.strip().split("\n"):
                if line:
                    # Alpine's "apk info" is just a list of package names with versions
                    packages.append({"name": line, "version": "unknown"})
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Error collecting packages: {e}")
    return packages

# --- 3. CIS Security Checks ---

def _run_shell_command(command):
    """A helper to run shell commands and return their output."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return None, str(e)

def check_root_login():
    """CIS 5.2.4: Ensure SSH root login is disabled."""
    file_path = "/etc/ssh/sshd_config"
    if not os.path.exists(file_path):
        return {"check": "CIS 5.2.4 SSH Root Login", "status": "fail", "evidence": f"{file_path} not found."}
    
    stdout, _ = _run_shell_command(f"grep -Ei '^\s*PermitRootLogin' {file_path}")
    if stdout and "yes" in stdout.lower():
        return {"check": "CIS 5.2.4 SSH Root Login", "status": "fail", "evidence": f"PermitRootLogin is set to 'yes' in {file_path}"}
    return {"check": "CIS 5.2.4 SSH Root Login", "status": "pass", "evidence": "Root login is disabled."}

def check_firewall_enabled():
    """CIS 3.5.1.1 & 3.5.2.1: Ensure firewall is enabled (ufw or firewalld)."""
    # Check for ufw
    stdout, _ = _run_shell_command("ufw status")
    if stdout and "Status: active" in stdout:
        return {"check": "CIS 3.5.x Firewall Enabled", "status": "pass", "evidence": "ufw is active."}
    
    # Check for firewalld
    stdout, _ = _run_shell_command("systemctl is-active firewalld")
    if stdout == "active":
        return {"check": "CIS 3.5.x Firewall Enabled", "status": "pass", "evidence": "firewalld is active."}
        
    return {"check": "CIS 3.5.x Firewall Enabled", "status": "fail", "evidence": "No active firewall (ufw or firewalld) found."}

def check_auditd_running():
    """CIS 4.1.1.2: Ensure auditd service is enabled and running."""
    stdout, _ = _run_shell_command("systemctl is-active auditd && systemctl is-enabled auditd")
    if "active" in stdout and "enabled" in stdout:
        return {"check": "CIS 4.1.1.2 Auditd Service", "status": "pass", "evidence": "auditd is active and enabled."}
    return {"check": "CIS 4.1.1.2 Auditd Service", "status": "fail", "evidence": "auditd is not active or not enabled."}

def check_apparmor_enabled():
    """CIS 1.6.1: Ensure AppArmor is enabled."""
    stdout, _ = _run_shell_command("systemctl is-active apparmor")
    if stdout == "active":
        return {"check": "CIS 1.6.1 AppArmor Enabled", "status": "pass", "evidence": "AppArmor is active."}
    # SELinux check for RHEL-based systems
    stdout, _ = _run_shell_command("sestatus")
    if stdout and "SELinux status:                 enabled" in stdout and "Current mode:                 enforcing" in stdout:
        return {"check": "CIS 1.6.1 SELinux Enabled", "status": "pass", "evidence": "SELinux is enabled and in enforcing mode."}
    return {"check": "CIS 1.6.1 AppArmor/SELinux", "status": "fail", "evidence": "Neither AppArmor nor enforcing SELinux is active."}

def check_world_writable_files():
    """CIS 6.1.4: Ensure no world-writable files exist."""
    # This can be slow. For a real agent, you might optimize this or run it less frequently.
    stdout, _ = _run_shell_command("find / -xdev -type f -perm -0002")
    if stdout:
        # Reporting only the first 10 for brevity
        files = "\n".join(stdout.split('\n')[:10])
        return {"check": "CIS 6.1.4 World-Writable Files", "status": "fail", "evidence": f"Found world-writable files, e.g.:\n{files}"}
    return {"check": "CIS 6.1.4 World-Writable Files", "status": "pass", "evidence": "No world-writable files found."}

def check_unused_filesystems():
    """CIS 1.1.1: Ensure mounting of cramfs, squashfs, udf is disabled."""
    disabled_modules = ["cramfs", "squashfs", "udf"]
    failures = []
    for module in disabled_modules:
        stdout, _ = _run_shell_command(f"modprobe -n -v {module}")
        lsmod_out, _ = _run_shell_command(f"lsmod | grep {module}")
        if "install /bin/true" not in stdout or lsmod_out:
            failures.append(module)
    
    if failures:
        return {"check": "CIS 1.1.1 Unused Filesystems", "status": "fail", "evidence": f"Modules not disabled: {', '.join(failures)}"}
    return {"check": "CIS 1.1.1 Unused Filesystems", "status": "pass", "evidence": "Required filesystems are disabled."}

def check_time_sync():
    """CIS 2.2.1.1: Ensure time synchronization is in use."""
    stdout_chrony, _ = _run_shell_command("systemctl is-active chrony")
    stdout_ntpd, _ = _run_shell_command("systemctl is-active ntpd")
    if stdout_chrony == "active" or stdout_ntpd == "active":
        service = "chrony" if stdout_chrony == "active" else "ntpd"
        return {"check": "CIS 2.2.1.1 Time Synchronization", "status": "pass", "evidence": f"{service} is active."}
    return {"check": "CIS 2.2.1.1 Time Synchronization", "status": "fail", "evidence": "No time synchronization service (chrony or ntpd) is active."}

def check_password_policies():
    """CIS 5.3.1: Ensure password creation requirements are configured."""
    file_path = "/etc/pam.d/common-password"
    if not os.path.exists(file_path):
        return {"check": "CIS 5.3.1 Password Policies", "status": "fail", "evidence": f"{file_path} not found."}
    
    stdout, _ = _run_shell_command(f"grep -E 'pam_pwquality.so|pam_cracklib.so' {file_path}")
    if "retry=3" in stdout and ("minlen=14" in stdout or "dcredit=-1" in stdout or "ucredit=-1" in stdout):
        return {"check": "CIS 5.3.1 Password Policies", "status": "pass", "evidence": "Password policies appear to be configured."}
    return {"check": "CIS 5.3.1 Password Policies", "status": "fail", "evidence": f"Password quality settings not found or insufficient in {file_path}."}

def check_gdm_autologin_disabled():
    """CIS 6.2.1: Ensure GDM auto-login is disabled."""
    # This check is for desktop environments.
    file_path = "/etc/gdm3/custom.conf"
    if not os.path.exists(file_path):
        return {"check": "CIS 6.2.1 GDM Auto-Login", "status": "pass", "evidence": f"GDM not installed or {file_path} not found (pass for servers)."}
        
    stdout, _ = _run_shell_command(f"grep -E 'AutomaticLoginEnable|AutomaticLogin'")
    if "true" in stdout.lower():
        return {"check": "CIS 6.2.1 GDM Auto-Login", "status": "fail", "evidence": f"Automatic login is enabled in {file_path}."}
    return {"check": "CIS 6.2.1 GDM Auto-Login", "status": "pass", "evidence": "Automatic login is disabled."}

# Additional check of my choice
def check_sudo_nopasswd():
    """Bonus Check: Ensure no users can use sudo without a password."""
    # Note: This is a simplified check. A real check would be more robust.
    stdout, _ = _run_shell_command("grep -r NOPASSWD /etc/sudoers.d/ /etc/sudoers")
    if stdout:
        return {"check": "Bonus: Sudo NOPASSWD", "status": "fail", "evidence": f"Users with NOPASSWD in sudoers:\n{stdout}"}
    return {"check": "Bonus: Sudo NOPASSWD", "status": "pass", "evidence": "No users found with NOPASSWD in sudoers configuration."}


def run_all_checks():
    """Runs all CIS checks and returns a list of results."""
    return [
        check_root_login(),
        check_firewall_enabled(),
        check_auditd_running(),
        check_apparmor_enabled(),
        check_world_writable_files(),
        check_unused_filesystems(),
        check_time_sync(),
        check_password_policies(),
        check_gdm_autologin_disabled(),
        check_sudo_nopasswd(),
    ]

# --- Main Execution ---
def main():
    """The main function to collect data and send it to the backend."""
    print("Starting data collection...")
    
    host_details = get_host_details()
    packages = get_installed_packages()
    cis_results = run_all_checks()
    
    payload = {
        "host_details": host_details,
        "installed_packages": packages,
        "cis_results": cis_results,
    }
    
    # The complete data payload
    final_payload = json.dumps(payload, indent=2)
    
    print("--- Collected Data ---")
    print(final_payload)
    print("----------------------")
    
    try:
        print(f"Sending data to {BACKEND_URL}...")
        response = requests.post(BACKEND_URL, json=payload, timeout=15)
        response.raise_for_status()  # Raise an exception for bad status codes
        print("Data sent successfully!")
        print("Server response:", response.json())
    except requests.exceptions.RequestException as e:
        print(f"Error sending data to backend: {e}")
        # In a real agent, you would save the data locally to retry later.

if __name__ == "__main__":
    main()
