"""Per-dtype extractors wrapping ZeppClient.

Each function performs the API call(s) for one data type and returns the
raw (already decoded) structure that the loader expects.
"""

from .client import ZeppClient


def extract_heart_rate(client: ZeppClient, date: str) -> list:
    return client.get_heart_rate(date)


def extract_sleep(client: ZeppClient, date: str) -> dict:
    return client.get_sleep(date)


def extract_steps(client: ZeppClient, date: str) -> dict:
    return client.get_steps(date)


def extract_stress(client: ZeppClient, from_date: str, to_date: str) -> list:
    return client.get_stress(from_date, to_date)


def extract_training_load(client: ZeppClient, from_date: str, to_date: str) -> list:
    return client.get_training_load(from_date, to_date)


def extract_sport_load(client: ZeppClient, from_date: str, to_date: str) -> list:
    return client.get_sport_load(from_date, to_date)


def extract_phn(client: ZeppClient, from_date: str, to_date: str) -> list:
    return client.get_phn(from_date, to_date)
