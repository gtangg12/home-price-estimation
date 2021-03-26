import os
import time
import math

import ssl, requests
import chromedriver_autoinstaller
from selenium import webdriver

from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# Ignore SSL certificate errors
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:21.0) Gecko/20100101 Firefox/21.0'
}

def get_API_Key():
    ''' Use headless Chrome/Chromium instance to scrape access key from the data-map-printing-background
        attribute of Apple Maps
    '''
    # query satellites.pro
    SAMPLE_KEY = r'1614125879_3642792122889215637_%2F_RwvhYZM5fKknqTdkXih2Wcu3s2f3Xea126uoIuDzUIY%3D'
    KEY_START = r'&accessKey='
    path = chromedriver_autoinstaller.install(cwd=True)
    options = webdriver.ChromeOptions()
    options.add_argument('headless')
    driver = webdriver.Chrome(executable_path=path, options=options)
    driver.get('https://satellites.pro/USA_map#37.405074,-94.284668,5')
    # wait for request
    time.sleep(5)

    # get access key from html element
    base = driver.find_element_by_css_selector('#map-canvas .leaflet-mapkit-mutant')
    data = base.get_attribute('data-map-printing-background')
    begin = data.find(KEY_START)
    contents = data[begin + len(KEY_START) : begin + int(1.5 * len(SAMPLE_KEY))]
    contents = contents[:contents.find('&')]
    return contents

ACCESS_KEY = get_API_Key()
print(ACCESS_KEY)


class TileBox:
    ''' Interface for interacting with scraped satellite tiles for bounded box on map

        Box defined by (box_tl, box_br), which denote the top-left and bottom-right corners
    '''
    def __init__(self, box_tl, box_br, name, verbose=False):
        assert box_tl[0] > box_br[0] and box_tl[1] < box_br[1]
        self.name = name
        self.dir = f'satellite_tiles/{name}'
        self.box_tl = box_tl
        self.box_br = box_br
        self.verbose = verbose

    def to_tile_xy(self, coords, zoom):
        ''' Returns tile indicies (x, y) given (lat, long)'''
        lat, long = coords
        n = 2 ** zoom
        lat = lat * math.pi / 180.0 # convert to rad
        tile_x = n * ((long + 180) / 360)
        tile_y = n * (1 - (math.log(math.tan(lat) + 1 / math.cos(lat)) / math.pi)) / 2
        return round(tile_x), round(tile_y)

    def scrape_tile(self, tile_xy, zoom):
        ''' Scrapes tile given its (x, y) indicies and zoom'''
        tile_x, tile_y = tile_xy
        tilepath = self.dir + f'/{tile_x}_{tile_y}_{zoom}.jpg'
        if os.path.exists(tilepath):
            if self.verbose: print(tilepath + ' already exists')
            return

        req_url = f'https://sat-cdn3.apple-mapkit.com/tile?style=7&size=1&scale=1&z={zoom}&x={tile_x}&y={tile_y}&v=9062&accessKey={ACCESS_KEY}'
        r = requests.get(req_url, headers= headers)
        if 'Access Denied' in str(r.content):
            raise Exception(f'Access Denied for Tile {x}_{y}')

        with open(tilepath, 'wb') as fout:
            fout.write(r.content)
        if self.verbose: print(tilepath + ' written')

    def scrape_all_tiles(self, zoom=19):
        if os.path.exists(self.dir):
            if self.verbose: print("Box already tiled")
            return
        os.mkdir(self.dir)

        tl_tile_x, tl_tile_y = self.to_tile_xy(box_tl, zoom)
        br_tile_x, br_tile_y = self.to_tile_xy(box_br, zoom)
        if self.verbose:
            print(f'Tiling x from {tl_tile_x} {br_tile_x}')
            print(f'Tiling y from {tl_tile_y} {br_tile_y}')
        for i in range(tl_tile_x, br_tile_x + 1):
            for j in range(tl_tile_y, br_tile_y + 1):
                self.scrape_tile((i, j), zoom)
        if self.verbose: print("Box tiled")

    def satellite_tile(self, location):
        lat, long = location.latitude, location.longitude

    ''' TODO: Add additional functionality i.e. surrounding area -> graph and what not'''
    ''' support metrics as described in https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5740675/ '''


box_tl = (31.4897, 73.6518)
box_br = (31.4867, 73.6558)
farm = TileBox(box_tl, box_br, 'farm', verbose=True)
farm.scrape_all_tiles()


geotool = Nominatim(user_agent='mit-pakistan-computer-vision')
geocode = RateLimiter(geotool.geocode, min_delay_seconds=1,
                      return_value_on_exception=None)

def location_info(arg):
    ''' Returns geopy.Location object given coords tuple (lat, long) or address string
    '''
    if isinstance(arg, tuple):
        return geocode.reverse(arg)
    return geocode(arg)
