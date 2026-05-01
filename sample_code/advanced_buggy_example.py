"""
sample_code/advanced_buggy_example.py
--------------------------------------
A realistic e-commerce backend simulation.
Contains 20+ intentional bugs, security vulnerabilities, and code smells
spread across multiple classes and functions.
DO NOT USE IN PRODUCTION.
"""

import os
import re
import json
import time
import pickle
import hashlib
import sqlite3
import subprocess
import threading
from datetime import datetime


# ── SECURITY: Hardcoded production credentials ────────────────────────────────
DB_HOST = "prod-db.internal.company.com"
DB_USER = "admin"
DB_PASS = "Sup3rS3cr3tP@ssw0rd"
SECRET_KEY = "sk-prod-abc123xyz789-NEVER-SHARE"
PAYMENT_API_KEY = "pk_live_51HG7dKJH29sKal9"
JWT_SECRET = "my_jwt_secret_do_not_share"
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


# ── DATABASE LAYER ─────────────────────────────────────────────────────────────

class DatabaseManager:
    """Manages database connections and queries for the e-commerce platform."""

    def __init__(self):
        self.connection = sqlite3.connect("ecommerce.db")
        self.cursor = self.connection.cursor()

    def get_user_by_credentials(self, username, password):
        """Authenticate a user by username and password."""
        # SECURITY: SQL injection via direct string formatting
        query = "SELECT * FROM users WHERE username='%s' AND password='%s'" % (username, password)
        self.cursor.execute(query)
        return self.cursor.fetchone()

    def get_product(self, product_id):
        """Fetch a product by its ID."""
        # SECURITY: SQL injection via concatenation
        query = "SELECT * FROM products WHERE id=" + str(product_id) + " AND active=1"
        self.cursor.execute(query)
        return self.cursor.fetchone()

    def search_products(self, search_term):
        """Search for products by name."""
        # SECURITY: SQL injection in LIKE clause
        query = f"SELECT * FROM products WHERE name LIKE '%{search_term}%'"
        self.cursor.execute(query)
        return self.cursor.fetchall()

    def update_user_balance(self, user_id, amount):
        """Update user account balance."""
        # BUG: No transaction, no rollback on failure
        # BUG: No validation that amount is positive
        self.cursor.execute(
            "UPDATE accounts SET balance = balance + " + str(amount) + " WHERE user_id=" + str(user_id)
        )
        self.connection.commit()

    def save_order(self, order_data):
        """Save a new order to the database."""
        # BUG: No error handling, connection never closed
        query = """INSERT INTO orders (user_id, product_id, quantity, total, status)
                   VALUES (?, ?, ?, ?, ?)"""
        self.cursor.execute(query, (
            order_data['user_id'],
            order_data['product_id'],
            order_data['quantity'],
            order_data['total'],
            'pending'
        ))
        self.connection.commit()
        # BUG: Returns None implicitly instead of order ID
        last_id = self.cursor.lastrowid

    def close(self):
        self.connection.close()


# ── USER MANAGEMENT ───────────────────────────────────────────────────────────

class UserManager:
    """Handles user registration, authentication, and session management."""

    # BUG: Mutable default argument - shared across all instances
    def __init__(self, active_sessions={}):
        self.db = DatabaseManager()
        self.active_sessions = active_sessions
        self.failed_attempts = {}

    def register_user(self, username, password, email):
        """Register a new user account."""
        # SECURITY: MD5 used for password hashing - cryptographically broken
        hashed = hashlib.md5(password.encode()).hexdigest()

        # BUG: No email format validation
        # BUG: No password strength check
        # BUG: No duplicate username check before insert

        user_data = {
            'username': username,
            'password': hashed,
            'email': email,
            'created_at': datetime.now(),
            'role': 'admin'  # BUG: Every new user gets admin role
        }

        try:
            conn = sqlite3.connect("ecommerce.db")
            conn.execute(
                "INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)",
                (username, hashed, email, user_data['role'])
            )
            conn.commit()
            # BUG: Connection never closed if exception occurs before here
            conn.close()
        except:
            # SMELL: Bare except swallows ALL exceptions including KeyboardInterrupt
            pass

        return user_data

    def login(self, username, password):
        """Authenticate user and create session."""
        # SECURITY: MD5 comparison - weak hash
        hashed = hashlib.md5(password.encode()).hexdigest()
        user = self.db.get_user_by_credentials(username, hashed)

        if user:
            # SECURITY: Predictable session token - MD5 of username+timestamp
            session_token = hashlib.md5(
                (username + str(time.time())).encode()
            ).hexdigest()
            self.active_sessions[session_token] = {
                'user': user,
                'expires': time.time() + 3600
            }
            # SECURITY: Returning password hash in session data
            return {'token': session_token, 'user': user}

        # BUG: No rate limiting on failed attempts
        return None

    def get_session_user(self, token):
        """Get the user associated with a session token."""
        session = self.active_sessions.get(token)
        # BUG: No expiry check - sessions never actually expire
        if session:
            return session['user']
        return None

    def change_password(self, user_id, old_password, new_password):
        """Change a user's password."""
        # BUG: old_password is never actually verified
        # SECURITY: MD5 still used
        new_hash = hashlib.md5(new_password.encode()).hexdigest()
        conn = sqlite3.connect("ecommerce.db")
        conn.execute(
            "UPDATE users SET password=? WHERE id=?",
            (new_hash, user_id)
        )
        conn.commit()
        # BUG: conn never closed
        return True

    def delete_user(self, requesting_user_id, target_user_id):
        """Delete a user account."""
        # SECURITY: No authorization check - any user can delete any other user
        conn = sqlite3.connect("ecommerce.db")
        conn.execute("DELETE FROM users WHERE id=?", (target_user_id,))
        conn.commit()
        conn.close()
        return True


# ── PAYMENT PROCESSING ────────────────────────────────────────────────────────

class PaymentProcessor:
    """Handles payment processing and transaction management."""

    def __init__(self):
        self.api_key = PAYMENT_API_KEY
        self.transactions = []

    def process_payment(self, amount, card_number, cvv, expiry):
        """Process a credit card payment."""
        # SECURITY: Logging sensitive card data
        print(f"Processing payment: card={card_number}, cvv={cvv}, amount={amount}")

        # BUG: No amount validation - negative amounts allowed (refund exploit)
        if amount == 0:
            return False

        # SECURITY: Storing raw card number in memory
        transaction = {
            'card_number': card_number,  # PCI-DSS violation
            'cvv': cvv,                  # PCI-DSS violation
            'amount': amount,
            'timestamp': datetime.now().isoformat()
        }
        self.transactions.append(transaction)

        # SECURITY: Storing transaction log with card data to disk
        with open("transaction_log.txt", "a") as f:
            f.write(json.dumps(transaction) + "\n")

        return True

    def calculate_total(self, items):
        """Calculate total price for a list of items."""
        total = 0
        for item in items:
            # BUG: KeyError if 'price' or 'quantity' missing - no validation
            total += item['price'] * item['quantity']

        # BUG: Floating point arithmetic used for money calculations
        # Should use Decimal for currency
        discount = total * 0.1
        final = total - discount
        return final

    def refund(self, transaction_id, amount):
        """Process a refund for a transaction."""
        # BUG: transaction_id never validated against actual transactions
        # SECURITY: No maximum refund amount check - can refund more than paid
        # BUG: amount type never checked - string "999999" would cause issues
        self.db.update_user_balance(transaction_id, amount)
        return True


# ── FILE MANAGEMENT ───────────────────────────────────────────────────────────

class FileManager:
    """Handles file uploads and downloads for product images and user data."""

    UPLOAD_DIR = "/var/www/uploads/"

    def save_upload(self, filename, content):
        """Save an uploaded file to the server."""
        # SECURITY: Path traversal - filename not sanitised
        # Attacker can use "../../etc/passwd" as filename
        filepath = self.UPLOAD_DIR + filename
        with open(filepath, 'wb') as f:
            f.write(content)
        return filepath

    def get_file(self, filename):
        """Retrieve a file by name."""
        # SECURITY: Path traversal vulnerability
        filepath = self.UPLOAD_DIR + filename
        with open(filepath, 'rb') as f:
            return f.read()

    def process_image(self, image_path):
        """Process and resize an uploaded image using ImageMagick."""
        # SECURITY: Shell injection via unsanitised image_path
        cmd = f"convert {image_path} -resize 800x600 {image_path}_resized.jpg"
        subprocess.run(cmd, shell=True)

    def load_user_preferences(self, pref_file):
        """Load saved user preferences from a file."""
        # SECURITY: Unsafe deserialisation with pickle
        with open(pref_file, 'rb') as f:
            return pickle.load(f)

    def execute_report_script(self, script_name, params):
        """Execute a reporting script with given parameters."""
        # SECURITY: Command injection - params injected directly into shell
        cmd = f"python reports/{script_name}.py --params {params}"
        result = subprocess.run(cmd, shell=True, capture_output=True)
        return result.stdout


# ── NOTIFICATION SYSTEM ───────────────────────────────────────────────────────

class NotificationService:
    """Sends email and SMS notifications to users."""

    def send_email(self, recipient, subject, body, template=None):
        """Send an email notification."""
        # BUG: template parameter accepted but completely ignored
        # BUG: No input validation on recipient email address
        # SMELL: Function does nothing - missing implementation
        email_data = {
            'to': recipient,
            'subject': subject,
            'body': body
        }
        # BUG: Just prints instead of actually sending
        print(f"Sending email to {recipient}")

    def notify_all_users(self, message, user_list=[]):
        """Send a notification to all users in the list."""
        # BUG: Mutable default argument - list persists between calls
        results = []
        for user in user_list:
            # BUG: No error handling - one failure stops all notifications
            self.send_email(user['email'], 'Notification', message)
            results.append(user['email'])
        return results

    def send_bulk_sms(self, phone_numbers, message):
        """Send SMS to multiple phone numbers."""
        # BUG: Thread created but never joined - fire and forget with no error handling
        for number in phone_numbers:
            t = threading.Thread(target=self._send_sms, args=(number, message))
            t.start()
            # BUG: Thread reference not stored - cannot be managed or cancelled

    def _send_sms(self, number, message):
        """Internal SMS sender."""
        # SECURITY: Logging phone numbers
        print(f"SMS to {number}: {message}")


# ── REPORTING ENGINE ──────────────────────────────────────────────────────────

class ReportEngine:
    """Generates business reports and analytics."""

    def generate_sales_report(self, start_date, end_date, format="csv"):
        """Generate a sales report for the given date range."""
        # BUG: format shadows Python builtin 'format'
        # BUG: start_date and end_date never validated

        conn = sqlite3.connect("ecommerce.db")
        # SECURITY: f-string SQL injection
        query = f"SELECT * FROM orders WHERE created_at BETWEEN '{start_date}' AND '{end_date}'"
        results = conn.execute(query).fetchall()
        # BUG: conn never closed

        if format == "csv":
            return self._to_csv(results)
        elif format == "json":
            return json.dumps(results)
        # BUG: No else/default - returns None implicitly for unknown formats

    def _to_csv(self, data):
        """Convert query results to CSV format."""
        # BUG: No handling for empty data
        # BUG: No escaping of commas in data values
        output = ""
        for row in data:
            output += ",".join(str(x) for x in row) + "\n"
        return output

    def evaluate_formula(self, formula):
        """Evaluate a custom analytics formula entered by the user."""
        # SECURITY: eval() on user input - remote code execution
        result = eval(formula)
        return result

    def run_custom_query(self, user_query):
        """Run a custom SQL query provided by an admin user."""
        # SECURITY: Direct execution of user-supplied SQL - SQL injection
        # BUG: No authorization check
        conn = sqlite3.connect("ecommerce.db")
        result = conn.execute(user_query).fetchall()
        conn.close()
        return result


# ── CACHE LAYER ───────────────────────────────────────────────────────────────

# SMELL: Global mutable state - shared across the entire application
_cache = {}
_cache_hits = 0
_cache_misses = 0


def get_cached(key):
    """Retrieve a value from the cache."""
    global _cache_hits, _cache_misses
    if key in _cache:
        _cache_hits += 1
        # BUG: No TTL/expiry - cache grows forever
        return _cache[key]
    _cache_misses += 1
    return None


def set_cached(key, value):
    """Store a value in the cache."""
    # BUG: No maximum size limit - unbounded memory growth
    # BUG: Not thread-safe - race condition in multi-threaded environments
    _cache[key] = value


# ── UTILITY FUNCTIONS ─────────────────────────────────────────────────────────

def validate_email(email):
    """Validate an email address format."""
    # BUG: Regex too permissive - accepts invalid emails
    pattern = r".+@.+"
    return re.match(pattern, email) is not None


def calculate_shipping(weight, destination):
    """Calculate shipping cost based on weight and destination."""
    # BUG: Magic numbers with no explanation
    if destination == "local":
        return weight * 1.5
    elif destination == "national":
        return weight * 3.2
    elif destination == "international":
        return weight * 7.8
    # BUG: Returns None for unknown destination - caller not warned


def parse_config(config_file):
    """Load application configuration from a file."""
    # SECURITY: Unsafe pickle deserialisation of config file
    with open(config_file, 'rb') as f:
        config = pickle.load(f)

    # BUG: No validation of loaded config structure
    return config


def retry_operation(func, max_retries):
    """Retry a failed operation up to max_retries times."""
    for i in range(max_retries):
        try:
            return func()
        except Exception as e:
            # SMELL: Swallowing exception details - using bare print
            print("Error occurred, retrying...")
            # BUG: No exponential backoff - hammers the failing service
            time.sleep(1)
    # BUG: Returns None after all retries fail - caller not warned


def format_price(amount):
    """Format a price for display."""
    # BUG: No handling for None input
    # BUG: No handling for negative values
    # BUG: Floating point - should use Decimal
    return f"${amount:.2f}"


def get_env_config():
    """Load sensitive configuration from environment."""
    return {
        # SECURITY: Falls back to hardcoded secrets if env vars missing
        'db_pass': os.environ.get('DB_PASS', DB_PASS),
        'secret_key': os.environ.get('SECRET_KEY', SECRET_KEY),
        'payment_key': os.environ.get('PAYMENT_KEY', PAYMENT_API_KEY),
    }


# ── MAIN APPLICATION ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    # BUG: Instantiating DatabaseManager without checking DB exists
    db = DatabaseManager()
    users = UserManager()
    payments = PaymentProcessor()
    files = FileManager()
    reports = ReportEngine()

    # Demo: register and login
    user = users.register_user("testuser", "password123", "test@test.com")
    session = users.login("testuser", "password123")

    # Demo: process a payment (with fake card data)
    payments.process_payment(99.99, "4111111111111111", "123", "12/26")

    # Demo: generate a report
    report = reports.generate_sales_report("2024-01-01", "2024-12-31")

    # Demo: evaluate a formula (DANGEROUS)
    result = reports.evaluate_formula("2 + 2")

    print("Application started successfully")