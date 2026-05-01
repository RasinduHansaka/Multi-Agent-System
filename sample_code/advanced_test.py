"""
sample_code/advanced_test.py
----------------------------
An advanced test file to evaluate the Code Review MAS.
Contains complex logic bugs, anti-patterns, and security vulnerabilities.
"""

import os
import sqlite3
import hashlib
import requests
import subprocess
import tempfile
import yaml

SECRET_API_TOKEN = "ghp_1234567890abcdefghijklmnopqrstuvwxyz" # SECURITY: Hardcoded Secret

class UserManager:
    def __init__(self, db_path="users.db"):
        self.db_path = db_path
        
    def add_user(self, username, role="user", roles_list=[]):
        # BUG/ANTI-PATTERN: Mutable default argument 'roles_list=[]'
        roles_list.append(role)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # SECURITY: SQL Injection
            query = f"INSERT INTO users (username, roles) VALUES ('{username}', '{','.join(roles_list)}')"
            cursor.execute(query)
            conn.commit()
        except:
            # BUG/ANTI-PATTERN: Bare except
            print("Failed to add user")
            
    def fetch_user_data_from_url(self, url):
        # SECURITY: SSRF / Unvalidated URL input
        response = requests.get(url)
        return response.json()
        
def process_data(data, list=None):
    # BUG/ANTI-PATTERN: Shadowing built-in 'list'
    if list is None:
        list = []
    
    # SECURITY: Insecure use of eval
    eval(data)
    
def legacy_hashing(password):
    # SECURITY: Weak cryptography MD5
    m = hashlib.md5()
    m.update(password.encode('utf-8'))
    return m.hexdigest()

def backup_database(db_name):
    # SECURITY: Command Injection via shell=True
    cmd = "tar -czvf backup.tar.gz " + db_name
    subprocess.Popen(cmd, shell=True)

def parse_config(yaml_string):
    # SECURITY: Unsafe yaml loading
    return yaml.load(yaml_string)
