#!/usr/bin/env python3
"""
SaaS Security Agent
Collects system information and security checks from Linux hosts
Sends data to AWS API Gateway for processing
"""

import json
import platform
import subprocess
import socket
import requests
import os

# Configuration
# I learned you can use environment variables to keep credentials secure
# instead of hardcoding them in the script
API_GATEWAY_ENDPOINT = os.environ.get('API_GATEWAY_ENDPOINT', '')
API_KEY = os.environ.get('API_KEY', '')

# For local testing during development, fallback to localhost
BACKEND_URL = os.environ.get('BACKEND_URL', 'http://127.0.0.1:8000/ingest')

# Figure out which endpoint to use based on what's configured
if API_GATEWAY_ENDPOINT:
    INGEST_URL = f"{API_GATEWAY_ENDPOINT}/ingest"
    USE_API_GATEWAY = True
else:
    INGEST_URL = BACKEND_URL
    USE_API_GATEWAY = False

AGENT_VERSION = "1.0.0"

def get_host_details():
    """
    Collect basic information about this machine
    Using Python's platform and socket libraries - these work on all Linux distros
    """
    details = {
        "hostname": socket.gethostname(),
        "os_type": platform.system(),
        "os_version": platform.release(),
    }
    return details


def get_installed_packages():
    """
    Get list of installed software packages
    Different Linux distros use different package managers, so we check for each one
    dpkg = Debian/Ubuntu, rpm = RHEL/CentOS, apk = Alpine
    """
    packages = []
    
    try:
        # Try dpkg first (used by Ubuntu, Debian)
        check_dpkg = subprocess.run(["which", "dpkg"], capture_output=True, text=True)
        if check_dpkg.stdout:
            # dpkg-query lists all packages - using format string to get name and version
            result = subprocess.run(
                ["dpkg-query", "-W", "-f=${Package}\t${Version}\n"], 
                capture_output=True, 
                text=True, 
                check=True
            )
            for line in result.stdout.strip().split("\n"):
                if line:  # Skip empty lines
                    parts = line.split("\t")
                    if len(parts) == 2:
                        packages.append({"name": parts[0], "version": parts[1]})
        
        # Try rpm if dpkg not found (RHEL, CentOS, Fedora)
        elif subprocess.run(["which", "rpm"], capture_output=True, text=True).stdout:
            # rpm -qa = query all packages
            result = subprocess.run(
                ["rpm", "-qa", "--qf", "%{NAME}\t%{VERSION}-%{RELEASE}\n"], 
                capture_output=True, 
                text=True, 
                check=True
            )
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split("\t")
                    if len(parts) == 2:
                        packages.append({"name": parts[0], "version": parts[1]})
        
        # Try apk if neither dpkg nor rpm found (Alpine Linux)
        elif subprocess.run(["which", "apk"], capture_output=True, text=True).stdout:
            result = subprocess.run(["apk", "info"], capture_output=True, text=True, check=True)
            for line in result.stdout.strip().split("\n"):
                if line:
                    # apk doesn't easily give version, so mark as unknown
                    packages.append({"name": line, "version": "unknown"})
    
    except (subprocess.CalledProcessError, FileNotFoundError) as err:
        print(f"Warning: Couldn't collect package list - {err}")
    
    return packages


# Security Check Functions
# Based on CIS (Center for Internet Security) benchmarks
# These are industry-standard security configurations

def _run_shell_command(command, timeout=60):
    """
    Helper function to run shell commands safely
    Added timeout to prevent hanging on slow commands
    """
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=timeout
        )
        return result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return None, f"Command timed out after {timeout} seconds."
    except Exception as err:
        return None, str(err)


def check_root_login():
    """
    CIS 5.2.4: SSH should not allow direct root login
    This is important because root has unlimited privileges
    """
    config_file = "/etc/ssh/sshd_config"
    
    if not os.path.exists(config_file):
        return {
            "check": "CIS 5.2.4 SSH Root Login", 
            "status": "fail", 
            "evidence": f"SSH config not found at {config_file}"
        }
    
    # Look for PermitRootLogin setting
    output, _ = _run_shell_command(f"grep -Ei '^\s*PermitRootLogin' {config_file}")
    
    if output and "yes" in output.lower():
        return {
            "check": "CIS 5.2.4 SSH Root Login", 
            "status": "fail", 
            "evidence": f"Root login is enabled in {config_file}"
        }
    
    return {
        "check": "CIS 5.2.4 SSH Root Login", 
        "status": "pass", 
        "evidence": "Root login is properly disabled"
    }

def check_firewall_enabled():
    """
    CIS 3.5.x: Check if a firewall is running
    Supports both ufw (Ubuntu) and firewalld (RHEL)
    """
    # Check ufw first (common on Ubuntu/Debian)
    output, _ = _run_shell_command("ufw status")
    if output and "Status: active" in output:
        return {
            "check": "CIS 3.5.x Firewall Enabled", 
            "status": "pass", 
            "evidence": "ufw firewall is active"
        }
    
    # Check firewalld (common on RHEL/CentOS)
    output, _ = _run_shell_command("systemctl is-active firewalld")
    if output == "active":
        return {
            "check": "CIS 3.5.x Firewall Enabled", 
            "status": "pass", 
            "evidence": "firewalld is active"
        }
    
    return {
        "check": "CIS 3.5.x Firewall Enabled", 
        "status": "fail", 
        "evidence": "No active firewall detected"
    }


def check_auditd_running():
    """
    CIS 4.1.1.2: Audit daemon should be running
    auditd logs security-relevant events - important for compliance
    """
    # Check if service is both active AND enabled (starts on boot)
    output, _ = _run_shell_command("systemctl is-active auditd && systemctl is-enabled auditd")
    
    if "active" in output and "enabled" in output:
        return {
            "check": "CIS 4.1.1.2 Auditd Service", 
            "status": "pass", 
            "evidence": "auditd is running and enabled"
        }
    
    return {
        "check": "CIS 4.1.1.2 Auditd Service", 
        "status": "fail", 
        "evidence": "auditd is not properly configured"
    }

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
    # This can be slow. We run it with a timeout.
    print("Running world-writable file check (30s timeout)...")
    stdout, stderr = _run_shell_command("find / -xdev -type f -perm -0002", timeout=30)

    if stderr and "timed out" in stderr:
        return {"check": "CIS 6.1.4 World-Writable Files", "status": "fail", "evidence": "Check timed out after 30 seconds."}

    if stdout:
        # Reporting only the first 10 for brevity
        files = "\n".join(stdout.split('\n')[:10])
        return {"check": "CIS 6.1.4 World-Writable Files", "status": "fail", "evidence": f"Found world-writable files, e.g.:\n{files}"}
    return {"check": "CIS 6.1.4 World-Writable Files", "status": "pass", "evidence": "No world-writable files found in the given time."}
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
        
    stdout, _ = _run_shell_command(f"grep -Ei 'AutomaticLoginEnable|AutomaticLogin' {file_path}")
    if stdout and "true" in stdout.lower():
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
    """
    Run all the security checks and collect results
    Returns a list of check results that we'll send to the backend
    """
    checks = [
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
    return checks


def main():
    """
    Main function - orchestrates the whole data collection process
    """
    print("=" * 60)
    print("SaaS Security Agent - Starting data collection...")
    print("=" * 60)
    
    # Show where we're sending data
    print(f"Target endpoint: {INGEST_URL}")
    print(f"Using API Gateway: {USE_API_GATEWAY}")
    print()
    
    # Step 1: Collect host information
    host_info = get_host_details()
    print(f"✓ Collected host details for: {host_info['hostname']}")
    
    # Step 2: Get list of installed software
    packages = get_installed_packages()
    print(f"✓ Collected {len(packages)} installed packages")
    
    # Step 3: Run security checks
    security_checks = run_all_checks()
    passed_count = sum(1 for check in security_checks if check['status'] == 'pass')
    print(f"✓ Completed {len(security_checks)} CIS security checks ({passed_count} passed)")
    print()
    
    # Build the complete data payload
    data_to_send = {
        "host_details": host_info,
        "installed_packages": packages,
        "cis_results": security_checks,
        "agent_version": AGENT_VERSION
    }
    
    # Set up HTTP headers
    headers = {'Content-Type': 'application/json'}
    
    # Add API key if we're using AWS
    if USE_API_GATEWAY and API_KEY:
        headers['x-api-key'] = API_KEY
        print("✓ API key added to request headers")
    elif USE_API_GATEWAY and not API_KEY:
        print("⚠️  WARNING: Using API Gateway but no API key set!")
        print("   Set API_KEY environment variable")
    
    # Debug mode - print the data we're about to send
    if os.environ.get('DEBUG', 'false').lower() == 'true':
        print("\n--- Collected Data (JSON) ---")
        print(json.dumps(data_to_send, indent=2))
        print("-----------------------------\n")
    
    # Try to send the data
    try:
        print(f"Sending data to {INGEST_URL}...")
        response = requests.post(INGEST_URL, json=data_to_send, headers=headers, timeout=30)
        response.raise_for_status()
        
        print("\n" + "=" * 60)
        print("✅ SUCCESS - Data sent successfully!")
        print("=" * 60)
        
        # Show what the server responded with
        try:
            response_json = response.json()
            print("\nServer Response:")
            print(json.dumps(response_json, indent=2))
        except json.JSONDecodeError:
            print(f"Response: {response.text}")
    
    except requests.exceptions.HTTPError as err:
        print("\n" + "=" * 60)
        print("❌ HTTP ERROR - Failed to send data")
        print("=" * 60)
        print(f"Status Code: {err.response.status_code}")
        print(f"Response: {err.response.text}")
        
        # Provide helpful hints based on the error
        if err.response.status_code == 401:
            print("\n💡 TIP: Check your API key configuration")
            print(f"   Current API_KEY: {'Set' if API_KEY else 'Not set'}")
        elif err.response.status_code == 403:
            print("\n💡 TIP: Your API key may be invalid or expired")
    
    except requests.exceptions.ConnectionError as err:
        print("\n" + "=" * 60)
        print("❌ CONNECTION ERROR - Cannot reach backend")
        print("=" * 60)
        print(f"Error: {err}")
        print("\n💡 TIPS:")
        print("   1. Check if backend is running")
        print("   2. Verify the endpoint URL is correct")
        print(f"   3. Current endpoint: {INGEST_URL}")
    
    except requests.exceptions.Timeout:
        print("\n" + "=" * 60)
        print("❌ TIMEOUT ERROR - Request timed out")
        print("=" * 60)
        print("The backend took too long to respond (>30 seconds)")
    
    except requests.exceptions.RequestException as err:
        print("\n" + "=" * 60)
        print("❌ REQUEST ERROR - Failed to send data")
        print("=" * 60)
        print(f"Error: {err}")
        print("\n💡 TIP: In production, would save data locally for retry")
    
    print("\n" + "=" * 60)
    print("Agent execution completed")
    print("=" * 60)


if __name__ == "__main__":
    main()
