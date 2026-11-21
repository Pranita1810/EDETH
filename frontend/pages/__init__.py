"""EDETH Frontend Pages Package"""
from frontend.pages.data_ingestion import DataIngestionPage
from frontend.pages.login import LoginPage
from frontend.pages.testing import TestingPage
from frontend.pages.user import UserPage
from frontend.pages.welcome import WelcomePage

__all__ = ["DataIngestionPage", "LoginPage", "TestingPage", "UserPage", "WelcomePage"]
