#!/usr/bin/env python3
"""
Security monitoring agent for Linux systems
Collects host info, packages, and CIS benchmark results
"""

import json
import platform
import subprocess
import socket
import requests
import os

# Config from environment variables
API_GATEWAY_ENDPOINT = os.environ.get('API_GATEWAY_ENDPOINT', '')
API_KEY = os.environ.get('API_KEY', '')
BACKEND_URL = os.environ.get('BACKEND_URL', 'http://127.0.0.1:8000/ingest')

# Determine target endpoint
if API_GATEWAY_ENDPOINT:
    INGEST_URL = f"{API_GATEWAY_ENDPOINT}/ingest"
    USE_API_GATEWAY = True
else:
    INGEST_URL = BACKEND_URL
    USE_API_GATEWAY = False

AGENT_VERSION = "1.0.0"

def get_host_details():
    """Get basic host information"""
    details = {
        "hostname": socket.gethostname(),
        "os_type": platform.system(),
        "os_version": platform.release(),
    }
    return details


def get_installed_packages():
    """Collect installed packages based on available package manager"""
    packages = []
    
    try:
        # Check for dpkg (Debian/Ubuntu)
        check_dpkg = subprocess.run(["which", "dpkg"], capture_output=True, text=True)
        if check_dpkg.stdout:
            result = subprocess.run(
                ["dpkg-query", "-W", "-f=${Package}\t${Version}\n"], 
                capture_output=True, 
                text=True, 
                check=True
            )
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split("\t")
                    if len(parts) == 2:
                        packages.append({"name": parts[0], "version": parts[1]})
        
        # Check for rpm (RHEL/CentOS)
        elif subprocess.run(["which", "rpm"], capture_output=True, text=True).stdout:
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
        
        # Check for apk (Alpine)
        elif subprocess.run(["which", "apk"], capture_output=True, text=True).stdout:
            result = subprocess.run(["apk", "info"], capture_output=True, text=True, check=True)
            for line in result.stdout.strip().split("\n"):
                if line:
                    packages.append({"name": line, "version": "unknown"})
    
    except (subprocess.CalledProcessError, FileNotFoundError) as err:
        print(f"Warning: Couldn't collect package list - {err}")
    
    return packages


def _run_shell_command(command, timeout=60):
    """Run shell command with timeout"""
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
    """Check if SSH root login is disabled"""
    config_file = "/etc/ssh/sshd_config"
    
    if not os.path.exists(config_file):
        return {
            "check": "CIS 5.2.4 SSH Root Login", 
            "status": "fail", 
            "evidence": f"SSH config not found at {config_file}"
        }
    
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
    """Check if firewall is active (ufw or firewalld)"""
    output, _ = _run_shell_command("ufw status")
    if output and "Status: active" in output:
        return {
            "check": "CIS 3.5.x Firewall Enabled", 
            "status": "pass", 
            "evidence": "ufw firewall is active"
        }
    
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
    """Check if auditd service is running"""
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
    """Check if AppArmor or SELinux is enabled"""
    stdout, _ = _run_shell_command("systemctl is-active apparmor")
    if stdout == "active":
        return {"check": "CIS 1.6.1 AppArmor Enabled", "status": "pass", "evidence": "AppArmor is active."}
    
    stdout, _ = _run_shell_command("sestatus")
    if stdout and "SELinux status:                 enabled" in stdout and "Current mode:                 enforcing" in stdout:
        return {"check": "CIS 1.6.1 SELinux Enabled", "status": "pass", "evidence": "SELinux is enabled and in enforcing mode."}
    return {"check": "CIS 1.6.1 AppArmor/SELinux", "status": "fail", "evidence": "Neither AppArmor nor enforcing SELinux is active."}

def check_world_writable_files():
    """Check for world-writable files"""
    stdout, stderr = _run_shell_command("find / -xdev -type f -perm -0002", timeout=30)

    if stderr and "timed out" in stderr:
        return {"check": "CIS 6.1.4 World-Writable Files", "status": "fail", "evidence": "Check timed out after 30 seconds."}

    if stdout:
        files = "\n".join(stdout.split('\n')[:10])
        return {"check": "CIS 6.1.4 World-Writable Files", "status": "fail", "evidence": f"Found world-writable files:\n{files}"}
    return {"check": "CIS 6.1.4 World-Writable Files", "status": "pass", "evidence": "No world-writable files found."}

def check_unused_filesystems():
    """Check if unused filesystems are disabled"""
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
    """Check if time sync service is running"""
    stdout_chrony, _ = _run_shell_command("systemctl is-active chrony")
    stdout_ntpd, _ = _run_shell_command("systemctl is-active ntpd")
    if stdout_chrony == "active" or stdout_ntpd == "active":
        service = "chrony" if stdout_chrony == "active" else "ntpd"
        return {"check": "CIS 2.2.1.1 Time Synchronization", "status": "pass", "evidence": f"{service} is active."}
    return {"check": "CIS 2.2.1.1 Time Synchronization", "status": "fail", "evidence": "No time sync service active."}

def check_password_policies():
    """Check password policy configuration"""
    file_path = "/etc/pam.d/common-password"
    if not os.path.exists(file_path):
        return {"check": "CIS 5.3.1 Password Policies", "status": "fail", "evidence": f"{file_path} not found."}
    
    stdout, _ = _run_shell_command(f"grep -E 'pam_pwquality.so|pam_cracklib.so' {file_path}")
    if "retry=3" in stdout and ("minlen=14" in stdout or "dcredit=-1" in stdout or "ucredit=-1" in stdout):
        return {"check": "CIS 5.3.1 Password Policies", "status": "pass", "evidence": "Password policies configured."}
    return {"check": "CIS 5.3.1 Password Policies", "status": "fail", "evidence": f"Password quality settings insufficient in {file_path}."}

def check_gdm_autologin_disabled():
    """Check if GDM auto-login is disabled"""
    file_path = "/etc/gdm3/custom.conf"
    if not os.path.exists(file_path):
        return {"check": "CIS 6.2.1 GDM Auto-Login", "status": "pass", "evidence": "GDM not installed (pass for servers)."}
        
    stdout, _ = _run_shell_command(f"grep -Ei 'AutomaticLoginEnable|AutomaticLogin' {file_path}")
    if stdout and "true" in stdout.lower():
        return {"check": "CIS 6.2.1 GDM Auto-Login", "status": "fail", "evidence": f"Automatic login is enabled in {file_path}."}
    return {"check": "CIS 6.2.1 GDM Auto-Login", "status": "pass", "evidence": "Automatic login is disabled."}

def check_sudo_nopasswd():
    """Check for passwordless sudo access"""
    stdout, _ = _run_shell_command("grep -r NOPASSWD /etc/sudoers.d/ /etc/sudoers")
    if stdout:
        return {"check": "Bonus: Sudo NOPASSWD", "status": "fail", "evidence": f"Users with NOPASSWD:\n{stdout}"}
    return {"check": "Bonus: Sudo NOPASSWD", "status": "pass", "evidence": "No passwordless sudo found."}


def run_all_checks():
    """Run all security checks"""
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
    print("=" * 60)
    print("Security Agent - Starting collection")
    print("=" * 60)
    print(f"Target: {INGEST_URL}")
    print()
    
    # Collect host info
    host_info = get_host_details()
    print(f"Host details: {host_info['hostname']}")
    
    # Get packages
    packages = get_installed_packages()
    print(f"Packages: {len(packages)}")
    
    # Run security checks
    security_checks = run_all_checks()
    passed_count = sum(1 for check in security_checks if check['status'] == 'pass')
    print(f"Security checks: {passed_count}/{len(security_checks)} passed")
    print()
    
    # Build payload
    data_to_send = {
        "host_details": host_info,
        "installed_packages": packages,
        "cis_results": security_checks,
        "agent_version": AGENT_VERSION
    }
    
    # Setup headers
    headers = {'Content-Type': 'application/json'}
    if USE_API_GATEWAY and API_KEY:
        headers['x-api-key'] = API_KEY
    
    # Send data
    try:
        print(f"Sending to {INGEST_URL}...")
        response = requests.post(INGEST_URL, json=data_to_send, headers=headers, timeout=30)
        response.raise_for_status()
        
        print("\n" + "=" * 60)
        print("Data sent successfully")
        print("=" * 60)
        
        try:
            response_json = response.json()
            print(json.dumps(response_json, indent=2))
        except json.JSONDecodeError:
            print(f"Response: {response.text}")
    
    except requests.exceptions.HTTPError as err:
        print(f"\nHTTP Error {err.response.status_code}")
        print(f"Response: {err.response.text}")
        if err.response.status_code == 401:
            print("Check API key configuration")
    
    except requests.exceptions.ConnectionError as err:
        print(f"\nConnection error: {err}")
        print("Check if backend is running")
    
    except requests.exceptions.Timeout:
        print("\nRequest timed out")
    
    except requests.exceptions.RequestException as err:
        print(f"\nRequest error: {err}")
    
    print("\n" + "=" * 60)
    print("Agent completed")
    print("=" * 60)


if __name__ == "__main__":
    main()
