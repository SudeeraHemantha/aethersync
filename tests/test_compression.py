import os
import sys
import time
import shutil
import unittest
import threading
import requests
import uvicorn

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import database
import app as backend_app

class TestResponseCompression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Point DB to separate DB
        cls.orig_db_path = database.DB_PATH
        cls.test_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_compression_aethersync.db"))
        database.DB_PATH = cls.test_db_path
        backend_app.DB_PATH = cls.test_db_path
        
        database.init_db()

        # Start uvicorn server in background thread
        cls.host = "127.0.0.1"
        cls.port = 8092
        cls.base_url = f"http://{cls.host}:{cls.port}"
        
        cls.config = uvicorn.Config(
            backend_app.app,
            host=cls.host,
            port=cls.port,
            log_level="error"
        )
        cls.server = uvicorn.Server(cls.config)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        
        # Give server a moment to start
        time.sleep(1.5)

    @classmethod
    def tearDownClass(cls):
        # Stop uvicorn server
        cls.server.should_exit = True
        cls.server_thread.join(timeout=5)
        
        # Restore paths and remove test DB
        database.DB_PATH = cls.orig_db_path
        backend_app.DB_PATH = cls.orig_db_path
        if os.path.exists(cls.test_db_path):
            try:
                os.remove(cls.test_db_path)
            except Exception:
                pass

    def test_gzip_compression_disabled_for_small_responses(self):
        # Dynamically add small route on the live app instance
        @backend_app.app.get("/api/test/small-response")
        def small_response():
            return {"data": "A" * 10}

        try:
            # Query the endpoint. Set Accept-Encoding: gzip
            headers = {"Accept-Encoding": "gzip"}
            r = requests.get(f"{self.base_url}/api/test/small-response", headers=headers)
            self.assertNotIn("gzip", r.headers.get("Content-Encoding", "").lower())
        finally:
            # Clean up route in-place
            routes_to_keep = [route for route in backend_app.app.router.routes if route.path != "/api/test/small-response"]
            backend_app.app.router.routes.clear()
            backend_app.app.router.routes.extend(routes_to_keep)

    def test_gzip_compression_enabled_for_large_responses(self):
        # Dynamically add large route
        @backend_app.app.get("/api/test/large-response")
        def large_response():
            return {"data": "A" * 2000}

        try:
            # Test with Accept-Encoding: identity (should not compress)
            headers_identity = {"Accept-Encoding": "identity"}
            r_no_gzip = requests.get(f"{self.base_url}/api/test/large-response", headers=headers_identity)
            self.assertNotIn("gzip", r_no_gzip.headers.get("Content-Encoding", "").lower())

            # Test with Accept-Encoding: gzip (should compress)
            headers_gzip = {"Accept-Encoding": "gzip"}
            r_gzip = requests.get(f"{self.base_url}/api/test/large-response", headers=headers_gzip)
            self.assertEqual(r_gzip.headers.get("Content-Encoding", "").lower(), "gzip")
        finally:
            # Clean up route in-place
            routes_to_keep = [route for route in backend_app.app.router.routes if route.path != "/api/test/large-response"]
            backend_app.app.router.routes.clear()
            backend_app.app.router.routes.extend(routes_to_keep)

if __name__ == "__main__":
    unittest.main()
