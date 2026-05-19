from locust import HttpUser, between, task

# This file is very minimal, checkout ai-python-container repo for better example


class ApiUser(HttpUser):
    wait_time = between(0.1, 1)  # Random wait 1-5s between tasks

    @task(10)
    def health_check(self):
        self.client.get("/health-check")

