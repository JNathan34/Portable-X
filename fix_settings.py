import os
import sys
import configparser
import shutil

def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def fix_settings():
    # Define the base directory relative to this script
    base_dir = get_base_dir()
    settings_path = os.path.join(base_dir, "PortableApps", "PortableX", "Data", "settings.ini")
    
    if not os.path.exists(settings_path):
        msg = "settings.ini not found."
        print(msg)
        return {"fixed": 0, "message": msg, "changed": False}

    print(f"Processing {settings_path}...")

    # 1. Build a map of lowercase relative paths to actual relative paths
    # We scan the base directory to find all executables and batch files
    path_map = {} # lowercase_rel_path (forward slash) -> actual_rel_path (forward slash)

    print("Scanning for applications...")
    scan_roots = []
    portableapps_dir = os.path.join(base_dir, "PortableApps")
    if os.path.exists(portableapps_dir):
        scan_roots.append(portableapps_dir)
    else:
        scan_roots.append(base_dir)

    skip_dirs = {"__pycache__", ".git", "Videos", "Pictures", "Music", "Downloads", "documents"}

    for scan_root in scan_roots:
        for root, dirs, files in os.walk(scan_root):
        # Skip some directories if needed
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for name in files:
                # We are interested in .exe and .bat files as they are likely keys
                if name.lower().endswith(".exe") or name.lower().endswith(".bat"):
                    full_path = os.path.join(root, name)
                    try:
                        # Get relative path
                        rel_path = os.path.relpath(full_path, base_dir)
                        # Normalize to forward slashes for consistency
                        rel_path_fwd = rel_path.replace("\\", "/")

                        path_map[rel_path_fwd.lower()] = rel_path_fwd
                    except ValueError:
                        pass

    # 2. Read existing settings
    # We use a raw config parser to preserve existing casing (even if it is wrong/lowercase)
    config = configparser.ConfigParser()
    config.optionxform = str
    try:
        config.read(settings_path)
    except Exception as e:
        print(f"Error reading settings.ini: {e}")
        return

    # 3. Fix keys
    fixed_count = 0
    
    for section in config.sections():
        # We need to collect changes first to avoid modifying dictionary during iteration
        replacements = {} # old_key -> new_key
        
        for key in config[section]:
            # Check if this key looks like a path (contains slashes)
            if "/" in key or "\\" in key:
                # Normalize key to lowercase forward slash for lookup
                key_norm = key.replace("\\", "/").lower()
                
                if key_norm in path_map:
                    correct_path = path_map[key_norm]
                    
                    # If the current key is different from correct path (case mismatch or slash mismatch)
                    if key != correct_path:
                        replacements[key] = correct_path
        
        # Apply replacements
        for old_key, new_key in replacements.items():
            # Get value from old key
            value = config[section][old_key]
            # Remove old key
            config.remove_option(section, old_key)
            # Set new key with value
            config.set(section, new_key, value)
            fixed_count += 1

    if fixed_count > 0:
        # Backup
        backup_path = settings_path + ".bak"
        shutil.copy2(settings_path, backup_path)
        print(f"Backed up original settings to {backup_path}")
        
        # Save
        with open(settings_path, 'w') as f:
            config.write(f)
        msg = f"Fixed {fixed_count} entries in settings.ini."
        print(msg)
        return {"fixed": fixed_count, "message": msg, "changed": True}
    else:
        msg = "No path casing issues found to fix."
        print(msg)
        return {"fixed": 0, "message": msg, "changed": False}

if __name__ == "__main__":
    fix_settings()
