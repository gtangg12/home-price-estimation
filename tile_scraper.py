import os
import time
import math
import itertools

import requests
import chromedriver_autoinstaller
from selenium import webdriver

from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter


class SatelliteSession:
    ''' Contains settings and other materials needed for satillite usage '''
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:21.0) Gecko/20100101 Firefox/21.0'
    }
    geotool = Nominatim(user_agent='mit-pakistan-computer-vision')
    geocode = RateLimiter(geotool.geocode, min_delay_seconds=1, return_value_on_exception=None)

    def __init__(self):
        self.api_key = self.get_api_key()

    def get_api_key(self):
        ''' Use headless Chrome/Chromium instance to scrape access key for Apple Maps from
            data-map-printing-background attribute of Satellites Pro
        '''
        sample_key = r'1614125879_3642792122889215637_%2F_RwvhYZM5fKknqTdkXih2Wcu3s2f3Xea126uoIuDzUIY%3D'
        key_begin = r'&accessKey='
        path = chromedriver_autoinstaller.install(cwd=True)
        options = webdriver.ChromeOptions()
        options.add_argument('headless')
        driver = webdriver.Chrome(executable_path=path, options=options)
        driver.get('https://satellites.pro/USA_map#37.405074,-94.284668,5')

        # wait for request to complete
        time.sleep(5)

        # extract key from html element
        base = driver.find_element_by_css_selector('#map-canvas .leaflet-mapkit-mutant')
        data = base.get_attribute('data-map-printing-background')
        begin = data.find(key_begin)
        contents = data[begin + len(key_begin): begin + int(1.5 * len(sample_key))]
        contents = contents[:contents.find('&')]
        return contents

    def location_info(arg):
        ''' Returns geopy.Location object given coords tuple (lat, long) or address string '''
        if isinstance(arg, tuple):
            return geocode.reverse(arg)
        return geocode(arg)


class TileBox:
    ''' Interface for interacting with scraped satellite tiles for bounded box on map, defined by
        the top-left and bottom-right corners (box_tl, box_br)
    '''
    def __init__(self, box_tl, box_br, name, session):
        assert box_tl[0] > box_br[0] and box_tl[1] < box_br[1]
        self.name = name
        self.dir = f'satellite_tiles/{name}'
        self.box_tl = box_tl
        self.box_br = box_br
        self.session = session

    def to_tile_xy(self, coords, zoom):
        lat, long = coords
        n = 2 ** zoom
        lat = lat * math.pi / 180.0
        tile_x = n * ((long + 180) / 360)
        tile_y = n * (1 - (math.log(math.tan(lat) + 1 / math.cos(lat)) / math.pi)) / 2
        return round(tile_x), round(tile_y)

    def scrape_tile(self, tile_xy, zoom):
        tile_x, tile_y = tile_xy
        req_url = f'https://sat-cdn3.apple-mapkit.com/tile?style=7&size=1&scale=1&z={zoom}&x={tile_x}&y={tile_y}&v=9062&accessKey={session.api_key}'
        r = requests.get(req_url, headers=session.headers)
        if 'Access Denied' in str(r.content):
            raise Exception(f'Access Denied for Tile {tile_x}_{tile_y}')
        path = self.dir + f'/{tile_x}_{tile_y}_{zoom}.jpg'
        with open(path, 'wb') as fout:
            fout.write(r.content)

    def scrape_tilebox(self, zoom=19):
        os.mkdir(self.dir)
        tl_x, tl_y = self.to_tile_xy(box_tl, zoom)
        br_x, br_y = self.to_tile_xy(box_br, zoom)
        for i, j in itertools.product(
            range(tl_x, br_x + 1),
            range(tl_y, br_y + 1)
        ):
            self.scrape_tile((i, j), zoom)

    ''' TODO: Add additional functionality i.e. surrounding area -> graph and what not'''
    ''' support metrics as described in https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5740675/ '''

if __name__ == '__main__':
    session = SatelliteSession()
    box_tl = (31.4897, 73.6518)
    box_br = (31.4867, 73.6558)
    farm = TileBox(box_tl, box_br, 'farm', session)
    farm.scrape_tilebox()
