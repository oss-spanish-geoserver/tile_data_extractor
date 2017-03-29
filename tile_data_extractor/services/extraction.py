import re
import json
import psqlparse
import os

from postgresql_log_parser.services import LogParserService
from postgresql_log_parser.repositories import FileRepository

from tile_data_extractor.utils import GeoUtils

class TileDataExtractionService(object):
    """
    Class whose main responsability is to process the parsed log file
    and build the final data with XYZ and affected table names
    """

    def __init__(self, repository):
        self.repository = repository
        self.storage_buffer = []
        self.parser_output_file = '/tmp/postgresql_parsed_log.log'
        self.parser_repository = FileRepository(self.parser_output_file)
        self.parser = LogParserService(self.parser_repository)

    def process(self, input_file):
        try:
            self.parser.parse(input_file)
            with open(self.parser_output_file, 'r+b') as f:
                for line in f:
                    line_json = json.loads(line)
                    if self.__valid_line(line_json):
                        data = self.__filter_query(line_json['query'])
                        if data:
                            # Add rest of data and store in file
                            data['timestamp'] = line_json['timestamp']
                            data['duration'] = line_json['duration']
                            data['user'] = line_json['user']
                            data['database'] = line_json['database']
                            self.storage_buffer.append(json.dumps(data))
                            self.__flush_storage_buffer(1000)
            self.__flush_storage_buffer()
        finally:
            os.remove(self.parser_output_file)

    def __valid_line(self, line):
        # We only want statement and execute commands discarding parser, bind...
        return 'command' in line and line['command'] in ['statement', 'execute']

    def __flush_storage_buffer(self, buffer_limit=0):
        if len(self.storage_buffer) >= buffer_limit:
            self.repository.store(self.storage_buffer)
            self.storage_buffer = []

    def __filter_query(self, query):
        query_stmt = psqlparse.parse(query)[0]
        if isinstance(query_stmt, dict):
            return None
        bbox_pattern = re.compile(r'.*(ST_AsTWKB\(ST_Simplify\(ST_RemoveRepeatedPoints|ST_AsBinary\(ST_Simplify\(ST_SnapToGrid|_zoomed).*(ST_MakeEnvelope\((?P<bbox_env>.*?)\,\d+\)|(ST_MakeEnvelope|BOX3D)\((?P<bbox_3d>.*?)\))', re.IGNORECASE)
        basemaps_pattern = re.compile(r'FROM\s(?P<basemaps_function>(\S+_zoomed|high_road(_labels)?|tunnels|bridges))',re.IGNORECASE)
        bbox_data = bbox_pattern.search(query)
        basemaps_functions = re.findall(basemaps_pattern, query)
        if bbox_data:
            coordinates = self.__coordinates_from_bbox_data(bbox_data.groupdict())
            if not self.__valid_coordinates(coordinates):
                return None
            xyz = GeoUtils.get_xyz_from_bbox(float(coordinates[0]),
                                             float(coordinates[1]),
                                             float(coordinates[2]),
                                             float(coordinates[3]),
                                             metatile=True)
            if xyz['z'] < 0 or xyz['z'] > 22:
                return None
            if basemaps_functions:
                tables = [t[0] for t in basemaps_functions]
                return {'xyz': xyz, 'tables': tables,
                        'basemaps': True, 'update': False}
            else:
                return {'xyz': xyz, 'tables': list(query_stmt.tables()),
                        'basemaps': False, 'update': False}
        elif query_stmt.statement in ['DELETE', 'INSERT', 'UPDATE']:
            return {'bbox': None, 'tables': list(query_stmt.tables()),
                    'basemaps': False, 'update': True}
        else:
            return None

    @staticmethod
    def __coordinates_from_bbox_data(bbox_data):
        """
        Extract bounding box coordinates from raw data
        """
        if bbox_data['bbox_3d']:
            bbox = []
            list_bbox = bbox_data['bbox_3d'].split(',')
            for part in list_bbox:
                bbox.extend(part.split(' '))
        elif bbox_data['bbox_env']:
            bbox = bbox_data['bbox_env'].split(',')
        return bbox

    def __valid_coordinates(self, coordinates):
        return len(coordinates) == 4
