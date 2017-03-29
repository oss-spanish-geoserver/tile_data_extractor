#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import unittest

from tile_data_extractor.services import TileDataExtractionService
from tile_data_extractor.repositories import InMemoryRepository

from ..test_helper import fixture_path

class TileDataExtractionServiceTestCase(unittest.TestCase):

    def setUp(self):
        self.repository = InMemoryRepository()
        self.service = TileDataExtractionService(self.repository)

    def test_should_extract_data_from_previous_process_correctly(self):
        self.service.process(fixture_path('processed_log.txt'))
        self.assertEqual(len(self.repository.get_all()), 4)

    def test_should_extract_data_from_user_queries_correctly(self):
        self.service.process(fixture_path('user_queries_processed.txt'))
        self.assertEqual(len(self.repository.get_all()), 2)