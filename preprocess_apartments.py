import csv
import random
import os
import json
import re
import pandas as pd
import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))

def sample_csvs(data_dir=current_dir):
    files = [
        "robinreal_data_withimages-1776461278845.csv",
        "sred_data_withmontageimages_latlong.csv",
        "structured_data_withimages-1776412361239.csv",
        "structured_data_withoutimages-1776412361239.csv"
    ]
    
    output = {}
    for filename in files:
        filepath = os.path.join(data_dir, filename)
        if not os.path.exists(filepath):
            output[filename] = {"error": f"File {filename} not found"}
            continue
        try:
            with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
                first_line = f.readline()
                if not first_line:
                    continue
                delimiter = ',' if ',' in first_line else ';'
                f.seek(0)
                
                reader = csv.reader(f, delimiter=delimiter)
                headers = next(reader)
                rows = []
                for row in reader:
                    rows.append(row)
                
                sampled = []
                for i in range(0, len(rows), 200):
                    chunk = rows[i:i+200]
                    if chunk:
                        sampled.append(random.choice(chunk))
                
                output[filename] = {
                    "headers": headers,
                    "samples": sampled[:3],
                    "total_rows": len(rows),
                    "sampled_count": len(sampled)
                }
        except Exception as e:
            output[filename] = {"error": str(e)}
            
    return output

def sample_headers(data_dir=current_dir):
    files = [
        "robinreal_data_withimages-1776461278845.csv",
        "sred_data_withmontageimages_latlong.csv",
        "structured_data_withimages-1776412361239.csv",
        "structured_data_withoutimages-1776412361239.csv"
    ]
    
    output = {}
    for filename in files:
        filepath = os.path.join(data_dir, filename)
        if not os.path.exists(filepath):
            output[filename] = {"error": f"File {filename} not found"}
            continue
        try:
            with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
                first_line = f.readline()
                if not first_line:
                    continue
                delimiter = ',' if ',' in first_line else ';'
                f.seek(0)
                
                reader = csv.reader(f, delimiter=delimiter)
                headers = next(reader)
                output[filename] = headers
        except Exception as e:
            output[filename] = str(e)

    return output

def feature_dictionary():
    return {'availability_flexible': {'neg': 'no availability flexible|not availability '
                                  'flexible|kein availability flexible|nicht '
                                  'availability flexible|sans availability '
                                  'flexible|pas de availability flexible|senza '
                                  'availability flexible|nessun availability '
                                  'flexible',
                           'pos': 'availability flexible|nach vereinbarung'},
 'availability_immediate': {'neg': 'no availability immediate|not availability '
                                   'immediate|kein availability '
                                   'immediate|nicht availability '
                                   'immediate|sans availability immediate|pas '
                                   'de availability immediate|senza '
                                   'availability immediate|nessun availability '
                                   'immediate',
                            'pos': 'availability immediate|ab sofort|de suite'},
 'bike_friendly': {'neg': 'no bike friendly|not bike friendly|kein bike '
                          'friendly|nicht bike friendly|sans bike friendly|pas '
                          'de bike friendly|senza bike friendly|nessun bike '
                          'friendly',
                   'pos': 'bike friendly|fahrradfreundlich|veloweg'},
 'car_dependent': {'neg': 'no car dependent|not car dependent|kein car '
                          'dependent|nicht car dependent|sans car '
                          'dependent|pas de car dependent|senza car '
                          'dependent|nessun car dependent',
                   'pos': 'car dependent|auto n[öo]tig|nur mit auto'},
 'close_to_airport': {'neg': 'no close to airport|not close to airport|kein '
                             'close to airport|nicht close to airport|sans '
                             'close to airport|pas de close to airport|senza '
                             'close to airport|nessun close to airport',
                      'pos': 'close to airport|flughafen|airport'},
 'close_to_bakery_cafe': {'neg': 'no close to bakery cafe|not close to bakery '
                                 'cafe|kein close to bakery cafe|nicht close '
                                 'to bakery cafe|sans close to bakery cafe|pas '
                                 'de close to bakery cafe|senza close to '
                                 'bakery cafe|nessun close to bakery cafe',
                          'pos': 'close to bakery cafe|b[äa]ckerei|cafe'},
 'close_to_bus_tram': {'neg': 'no close to bus tram|not close to bus tram|kein '
                              'close to bus tram|nicht close to bus tram|sans '
                              'close to bus tram|pas de close to bus '
                              'tram|senza close to bus tram|nessun close to '
                              'bus tram',
                       'pos': 'close to bus '
                              'tram|bushaltestelle|tram|haltestelle'},
 'close_to_fitness': {'neg': 'no close to fitness|not close to fitness|kein '
                             'close to fitness|nicht close to fitness|sans '
                             'close to fitness|pas de close to fitness|senza '
                             'close to fitness|nessun close to fitness',
                      'pos': 'close to fitness|fitness|sportplatz|sportanlage'},
 'close_to_highway': {'neg': 'no close to highway|not close to highway|kein '
                             'close to highway|nicht close to highway|sans '
                             'close to highway|pas de close to highway|senza '
                             'close to highway|nessun close to highway',
                      'pos': 'close to '
                             'highway|autobahn|autobahnanschluss|verkehrsg[üu]nstig'},
 'close_to_hospital': {'neg': 'no close to hospital|not close to hospital|kein '
                              'close to hospital|nicht close to hospital|sans '
                              'close to hospital|pas de close to '
                              'hospital|senza close to hospital|nessun close '
                              'to hospital',
                       'pos': 'close to hospital|spital|krankenhaus|arzt'},
 'close_to_kindergarten': {'neg': 'no close to kindergarten|not close to '
                                  'kindergarten|kein close to '
                                  'kindergarten|nicht close to '
                                  'kindergarten|sans close to kindergarten|pas '
                                  'de close to kindergarten|senza close to '
                                  'kindergarten|nessun close to kindergarten',
                           'pos': 'close to kindergarten|kindergarten|kita'},
 'close_to_restaurants': {'neg': 'no close to restaurants|not close to '
                                 'restaurants|kein close to restaurants|nicht '
                                 'close to restaurants|sans close to '
                                 'restaurants|pas de close to '
                                 'restaurants|senza close to '
                                 'restaurants|nessun close to restaurants',
                          'pos': 'close to '
                                 'restaurants|restaurant|gastronomie|essen'},
 'close_to_schools': {'neg': 'no close to schools|not close to schools|kein '
                             'close to schools|nicht close to schools|sans '
                             'close to schools|pas de close to schools|senza '
                             'close to schools|nessun close to schools',
                      'pos': 'close to schools|schule|primarschule|oberstufe'},
 'close_to_shopping_mall': {'neg': 'no close to shopping mall|not close to '
                                   'shopping mall|kein close to shopping '
                                   'mall|nicht close to shopping mall|sans '
                                   'close to shopping mall|pas de close to '
                                   'shopping mall|senza close to shopping '
                                   'mall|nessun close to shopping mall',
                            'pos': 'close to shopping '
                                   'mall|einkaufszentrum|mall'},
 'close_to_supermarket': {'neg': 'no close to supermarket|not close to '
                                 'supermarket|kein close to supermarket|nicht '
                                 'close to supermarket|sans close to '
                                 'supermarket|pas de close to '
                                 'supermarket|senza close to '
                                 'supermarket|nessun close to supermarket',
                          'pos': 'close to '
                                 'supermarket|migros|coop|denner|aldi|lidl|einkaufsm[öo]glichkeiten'},
 'close_to_train_station': {'neg': 'no close to train station|not close to '
                                   'train station|kein close to train '
                                   'station|nicht close to train station|sans '
                                   'close to train station|pas de close to '
                                   'train station|senza close to train '
                                   'station|nessun close to train station',
                            'pos': 'close to train station|bahnhof'},
 'close_to_university': {'neg': 'no close to university|not close to '
                                'university|kein close to university|nicht '
                                'close to university|sans close to '
                                'university|pas de close to university|senza '
                                'close to university|nessun close to '
                                'university',
                         'pos': 'close to '
                                'university|uni|eth|universit[äa]t|hochschule'},
 'commercial_allowed': {'neg': 'no commercial allowed|not commercial '
                               'allowed|kein commercial allowed|nicht '
                               'commercial allowed|sans commercial allowed|pas '
                               'de commercial allowed|senza commercial '
                               'allowed|nessun commercial allowed',
                        'pos': 'commercial allowed|gewerbe|b[üu]ro|praxis'},
 'commute_excellent': {'neg': 'no commute excellent|not commute excellent|kein '
                              'commute excellent|nicht commute excellent|sans '
                              'commute excellent|pas de commute '
                              'excellent|senza commute excellent|nessun '
                              'commute excellent',
                       'pos': 'commute excellent|hervorragende anbindung|top '
                              'lage|perfekt angebunden'},
 'condition_needs_renovation': {'neg': 'no condition needs renovation|not '
                                       'condition needs renovation|kein '
                                       'condition needs renovation|nicht '
                                       'condition needs renovation|sans '
                                       'condition needs renovation|pas de '
                                       'condition needs renovation|senza '
                                       'condition needs renovation|nessun '
                                       'condition needs renovation',
                                'pos': 'condition needs '
                                       'renovation|renovationsbed[üu]rftig|zum '
                                       'umbauen'},
 'condition_newly_renovated': {'neg': 'no condition newly renovated|not '
                                      'condition newly renovated|kein '
                                      'condition newly renovated|nicht '
                                      'condition newly renovated|sans '
                                      'condition newly renovated|pas de '
                                      'condition newly renovated|senza '
                                      'condition newly renovated|nessun '
                                      'condition newly renovated',
                               'pos': 'condition newly '
                                      'renovated|renoviert|saniert|frisch '
                                      'gestrichen'},
 'condition_well_maintained': {'neg': 'no condition well maintained|not '
                                      'condition well maintained|kein '
                                      'condition well maintained|nicht '
                                      'condition well maintained|sans '
                                      'condition well maintained|pas de '
                                      'condition well maintained|senza '
                                      'condition well maintained|nessun '
                                      'condition well maintained',
                               'pos': 'condition well maintained|gepflegt|gut '
                                      'erhalten'},
 'deposit_required': {'neg': 'no deposit required|not deposit required|kein '
                             'deposit required|nicht deposit required|sans '
                             'deposit required|pas de deposit required|senza '
                             'deposit required|nessun deposit required',
                      'pos': 'deposit required|kaution|mietzinsdepot'},
 'first_time_occupancy': {'neg': 'no first time occupancy|not first time '
                                 'occupancy|kein first time occupancy|nicht '
                                 'first time occupancy|sans first time '
                                 'occupancy|pas de first time occupancy|senza '
                                 'first time occupancy|nessun first time '
                                 'occupancy',
                          'pos': 'first time occupancy|erstbezug'},
 'floors_laminate': {'neg': 'no floors laminate|not floors laminate|kein '
                            'floors laminate|nicht floors laminate|sans floors '
                            'laminate|pas de floors laminate|senza floors '
                            'laminate|nessun floors laminate',
                     'pos': 'floors laminate|laminat'},
 'floors_tile': {'neg': 'no floors tile|not floors tile|kein floors tile|nicht '
                        'floors tile|sans floors tile|pas de floors tile|senza '
                        'floors tile|nessun floors tile',
                 'pos': 'floors tile|plattenboden|keramikplatten|fliesen'},
 'floors_wood_parquet': {'neg': 'no floors wood parquet|not floors wood '
                                'parquet|kein floors wood parquet|nicht floors '
                                'wood parquet|sans floors wood parquet|pas de '
                                'floors wood parquet|senza floors wood '
                                'parquet|nessun floors wood parquet',
                         'pos': 'floors wood parquet|parkett|holzboden|wood '
                                'floor'},
 'has_air_conditioning': {'neg': 'no has air conditioning|not has air '
                                 'conditioning|kein has air conditioning|nicht '
                                 'has air conditioning|sans has air '
                                 'conditioning|pas de has air '
                                 'conditioning|senza has air '
                                 'conditioning|nessun has air conditioning',
                          'pos': 'has air conditioning|klimaanlage|air '
                                 'condition'},
 'has_attic_storage': {'neg': 'no has attic storage|not has attic storage|kein '
                              'has attic storage|nicht has attic storage|sans '
                              'has attic storage|pas de has attic '
                              'storage|senza has attic storage|nessun has '
                              'attic storage',
                       'pos': 'has attic storage|estrich|attic storage'},
 'has_basement_hobby_room': {'neg': 'no has basement hobby room|not has '
                                    'basement hobby room|kein has basement '
                                    'hobby room|nicht has basement hobby '
                                    'room|sans has basement hobby room|pas de '
                                    'has basement hobby room|senza has '
                                    'basement hobby room|nessun has basement '
                                    'hobby room',
                             'pos': 'has basement hobby '
                                    'room|bastelraum|hobbyraum'},
 'has_bathtub': {'neg': 'no has bathtub|not has bathtub|kein has bathtub|nicht '
                        'has bathtub|sans has bathtub|pas de has bathtub|senza '
                        'has bathtub|nessun has bathtub',
                 'pos': 'has bathtub|badewanne|bathtub|badezimmer mit wanne'},
 'has_bicycle_room': {'neg': 'no has bicycle room|not has bicycle room|kein '
                             'has bicycle room|nicht has bicycle room|sans has '
                             'bicycle room|pas de has bicycle room|senza has '
                             'bicycle room|nessun has bicycle room',
                      'pos': 'has bicycle room|veloraum|fahrradkeller'},
 'has_built_in_wardrobes': {'neg': 'no has built in wardrobes|not has built in '
                                   'wardrobes|kein has built in '
                                   'wardrobes|nicht has built in '
                                   'wardrobes|sans has built in wardrobes|pas '
                                   'de has built in wardrobes|senza has built '
                                   'in wardrobes|nessun has built in wardrobes',
                            'pos': 'has built in '
                                   'wardrobes|einbauschr[äa]nke|einbauschrank|wardrobe'},
 'has_cellar_storage': {'neg': 'no has cellar storage|not has cellar '
                               'storage|kein has cellar storage|nicht has '
                               'cellar storage|sans has cellar storage|pas de '
                               'has cellar storage|senza has cellar '
                               'storage|nessun has cellar storage',
                        'pos': 'has cellar storage|keller|kellerabteil|cellar'},
 'has_dishwasher': {'neg': 'no has dishwasher|not has dishwasher|kein has '
                           'dishwasher|nicht has dishwasher|sans has '
                           'dishwasher|pas de has dishwasher|senza has '
                           'dishwasher|nessun has dishwasher',
                    'pos': 'has '
                           'dishwasher|geschirrsp[üu]ler|steamer|sp[üu]lmaschine|lave-vaisselle|lavastoviglie'},
 'has_fiber_internet': {'neg': 'no has fiber internet|not has fiber '
                               'internet|kein has fiber internet|nicht has '
                               'fiber internet|sans has fiber internet|pas de '
                               'has fiber internet|senza has fiber '
                               'internet|nessun has fiber internet',
                        'pos': 'has fiber internet|glasfaser|schnelles '
                               'internet'},
 'has_floor_heating': {'neg': 'no has floor heating|not has floor heating|kein '
                              'has floor heating|nicht has floor heating|sans '
                              'has floor heating|pas de has floor '
                              'heating|senza has floor heating|nessun has '
                              'floor heating',
                       'pos': 'has floor '
                              'heating|bodenheizung|fussbodenheizung'},
 'has_gallery_loft': {'neg': 'no has gallery loft|not has gallery loft|kein '
                             'has gallery loft|nicht has gallery loft|sans has '
                             'gallery loft|pas de has gallery loft|senza has '
                             'gallery loft|nessun has gallery loft',
                      'pos': 'has gallery loft|galerie'},
 'has_guest_toilet': {'neg': 'no has guest toilet|not has guest toilet|kein '
                             'has guest toilet|nicht has guest toilet|sans has '
                             'guest toilet|pas de has guest toilet|senza has '
                             'guest toilet|nessun has guest toilet',
                      'pos': 'has guest '
                             'toilet|g[äa]ste-wc|g[äa]stetoilette|separates '
                             'wc'},
 'has_heat_pump': {'neg': 'no has heat pump|not has heat pump|kein has heat '
                          'pump|nicht has heat pump|sans has heat pump|pas de '
                          'has heat pump|senza has heat pump|nessun has heat '
                          'pump',
                   'pos': 'has heat pump|w[äa]rmepumpe|erdsonde'},
 'has_high_ceilings': {'neg': 'no has high ceilings|not has high ceilings|kein '
                              'has high ceilings|nicht has high ceilings|sans '
                              'has high ceilings|pas de has high '
                              'ceilings|senza has high ceilings|nessun has '
                              'high ceilings',
                       'pos': 'has high ceilings|hohe '
                              'r[äa]ume|raumh[öo]he|high ceilings'},
 'has_large_windows': {'neg': 'no has large windows|not has large windows|kein '
                              'has large windows|nicht has large windows|sans '
                              'has large windows|pas de has large '
                              'windows|senza has large windows|nessun has '
                              'large windows',
                       'pos': 'has large windows|grosse fenster|bodentiefe '
                              'fenster|gewaltige fenster'},
 'has_loggia': {'neg': 'no has loggia|not has loggia|kein has loggia|nicht has '
                       'loggia|sans has loggia|pas de has loggia|senza has '
                       'loggia|nessun has loggia',
                'pos': 'has loggia|loggia'},
 'has_modern_kitchen': {'neg': 'no has modern kitchen|not has modern '
                               'kitchen|kein has modern kitchen|nicht has '
                               'modern kitchen|sans has modern kitchen|pas de '
                               'has modern kitchen|senza has modern '
                               'kitchen|nessun has modern kitchen',
                        'pos': 'has modern kitchen|moderne k[uü]che|neue '
                               'k[uü]che|modern kitchen'},
 'has_multiple_bathrooms': {'neg': 'no has multiple bathrooms|not has multiple '
                                   'bathrooms|kein has multiple '
                                   'bathrooms|nicht has multiple '
                                   'bathrooms|sans has multiple bathrooms|pas '
                                   'de has multiple bathrooms|senza has '
                                   'multiple bathrooms|nessun has multiple '
                                   'bathrooms',
                            'pos': 'has multiple bathrooms|2 badezimmer|zwei '
                                   'badezimmer|mehrere nasszellen'},
 'has_open_kitchen': {'neg': 'no has open kitchen|not has open kitchen|kein '
                             'has open kitchen|nicht has open kitchen|sans has '
                             'open kitchen|pas de has open kitchen|senza has '
                             'open kitchen|nessun has open kitchen',
                      'pos': 'has open kitchen|offene k[uü]che|open kitchen'},
 'has_playground': {'neg': 'no has playground|not has playground|kein has '
                           'playground|nicht has playground|sans has '
                           'playground|pas de has playground|senza has '
                           'playground|nessun has playground',
                    'pos': 'has playground|spielplatz'},
 'has_sauna': {'neg': 'no has sauna|not has sauna|kein has sauna|nicht has '
                      'sauna|sans has sauna|pas de has sauna|senza has '
                      'sauna|nessun has sauna',
               'pos': 'has sauna|sauna'},
 'has_smart_home': {'neg': 'no has smart home|not has smart home|kein has '
                           'smart home|nicht has smart home|sans has smart '
                           'home|pas de has smart home|senza has smart '
                           'home|nessun has smart home',
                    'pos': 'has smart home|smart home|digital|hausautomation'},
 'has_solar_panels': {'neg': 'no has solar panels|not has solar panels|kein '
                             'has solar panels|nicht has solar panels|sans has '
                             'solar panels|pas de has solar panels|senza has '
                             'solar panels|nessun has solar panels',
                      'pos': 'has solar panels|solar|photovoltaik'},
 'has_swimming_pool': {'neg': 'no has swimming pool|not has swimming pool|kein '
                              'has swimming pool|nicht has swimming pool|sans '
                              'has swimming pool|pas de has swimming '
                              'pool|senza has swimming pool|nessun has '
                              'swimming pool',
                       'pos': 'has swimming pool|pool|schwimmbad'},
 'has_terrace': {'neg': 'no has terrace|not has terrace|kein has terrace|nicht '
                        'has terrace|sans has terrace|pas de has terrace|senza '
                        'has terrace|nessun has terrace',
                 'pos': 'has terrace|terrasse|sitzplatz'},
 'has_tumbler_in_unit': {'neg': 'no has tumbler in unit|not has tumbler in '
                                'unit|kein has tumbler in unit|nicht has '
                                'tumbler in unit|sans has tumbler in unit|pas '
                                'de has tumbler in unit|senza has tumbler in '
                                'unit|nessun has tumbler in unit',
                         'pos': 'has tumbler in unit|tumbler|eigener '
                                'waschturm'},
 'has_walk_in_closet': {'neg': 'no has walk in closet|not has walk in '
                               'closet|kein has walk in closet|nicht has walk '
                               'in closet|sans has walk in closet|pas de has '
                               'walk in closet|senza has walk in closet|nessun '
                               'has walk in closet',
                        'pos': 'has walk in closet|ankleide|walk-in closet'},
 'has_walk_in_shower': {'neg': 'no has walk in shower|not has walk in '
                               'shower|kein has walk in shower|nicht has walk '
                               'in shower|sans has walk in shower|pas de has '
                               'walk in shower|senza has walk in shower|nessun '
                               'has walk in shower',
                        'pos': 'has walk in shower|regendusche|begehbare '
                               'dusche|walk-in dusche'},
 'has_washing_machine_in_unit': {'neg': 'no has washing machine in unit|not '
                                        'has washing machine in unit|kein has '
                                        'washing machine in unit|nicht has '
                                        'washing machine in unit|sans has '
                                        'washing machine in unit|pas de has '
                                        'washing machine in unit|senza has '
                                        'washing machine in unit|nessun has '
                                        'washing machine in unit',
                                 'pos': 'has washing machine in unit|eigene '
                                        'waschmaschine|eigener '
                                        'waschturm|waschmaschine in der '
                                        'wohnung'},
 'is_attic_flat': {'neg': 'no is attic flat|not is attic flat|kein is attic '
                          'flat|nicht is attic flat|sans is attic flat|pas de '
                          'is attic flat|senza is attic flat|nessun is attic '
                          'flat',
                   'pos': 'is attic flat|attika|dachwohnung|dachgeschoss'},
 'is_furnished': {'neg': 'no is furnished|not is furnished|kein is '
                         'furnished|nicht is furnished|sans is furnished|pas '
                         'de is furnished|senza is furnished|nessun is '
                         'furnished',
                  'pos': 'is furnished|m[öo]bliert|furnished'},
 'is_ground_floor': {'neg': 'no is ground floor|not is ground floor|kein is '
                            'ground floor|nicht is ground floor|sans is ground '
                            'floor|pas de is ground floor|senza is ground '
                            'floor|nessun is ground floor',
                     'pos': 'is ground floor|erdgeschoss|parterre'},
 'is_house': {'neg': 'no is house|not is house|kein is house|nicht is '
                     'house|sans is house|pas de is house|senza is '
                     'house|nessun is house',
              'pos': 'is house|haus|house|maison|casa'},
 'is_maisonette_duplex': {'neg': 'no is maisonette duplex|not is maisonette '
                                 'duplex|kein is maisonette duplex|nicht is '
                                 'maisonette duplex|sans is maisonette '
                                 'duplex|pas de is maisonette duplex|senza is '
                                 'maisonette duplex|nessun is maisonette '
                                 'duplex',
                          'pos': 'is maisonette duplex|maisonette|duplex'},
 'is_minergie_certified': {'neg': 'no is minergie certified|not is minergie '
                                  'certified|kein is minergie certified|nicht '
                                  'is minergie certified|sans is minergie '
                                  'certified|pas de is minergie '
                                  'certified|senza is minergie '
                                  'certified|nessun is minergie certified',
                           'pos': 'is minergie '
                                  'certified|minergie|-standard|energieeffizient'},
 'is_penthouse': {'neg': 'no is penthouse|not is penthouse|kein is '
                         'penthouse|nicht is penthouse|sans is penthouse|pas '
                         'de is penthouse|senza is penthouse|nessun is '
                         'penthouse',
                  'pos': 'is penthouse|penthouse'},
 'is_unfurnished': {'neg': 'no is unfurnished|not is unfurnished|kein is '
                           'unfurnished|nicht is unfurnished|sans is '
                           'unfurnished|pas de is unfurnished|senza is '
                           'unfurnished|nessun is unfurnished',
                    'pos': 'is unfurnished|unm[öo]bliert|unfurnished'},
 'is_wheelchair_accessible': {'neg': 'no is wheelchair accessible|not is '
                                     'wheelchair accessible|kein is wheelchair '
                                     'accessible|nicht is wheelchair '
                                     'accessible|sans is wheelchair '
                                     'accessible|pas de is wheelchair '
                                     'accessible|senza is wheelchair '
                                     'accessible|nessun is wheelchair '
                                     'accessible',
                              'pos': 'is wheelchair '
                                     'accessible|rollstuhlg[äa]ngig|rollstuhlgerecht'},
 'layout_open_plan': {'neg': 'no layout open plan|not layout open plan|kein '
                             'layout open plan|nicht layout open plan|sans '
                             'layout open plan|pas de layout open plan|senza '
                             'layout open plan|nessun layout open plan',
                      'pos': 'layout open plan|offener grundriss'},
 'layout_separated_rooms': {'neg': 'no layout separated rooms|not layout '
                                   'separated rooms|kein layout separated '
                                   'rooms|nicht layout separated rooms|sans '
                                   'layout separated rooms|pas de layout '
                                   'separated rooms|senza layout separated '
                                   'rooms|nessun layout separated rooms',
                            'pos': 'layout separated rooms|geschlossene '
                                   'zimmer'},
 'location_rural': {'neg': 'no location rural|not location rural|kein location '
                           'rural|nicht location rural|sans location rural|pas '
                           'de location rural|senza location rural|nessun '
                           'location rural',
                    'pos': 'location rural|l[äa]ndlich|auf dem '
                           'land|bauernhaus'},
 'location_suburban': {'neg': 'no location suburban|not location suburban|kein '
                              'location suburban|nicht location suburban|sans '
                              'location suburban|pas de location '
                              'suburban|senza location suburban|nessun '
                              'location suburban',
                       'pos': 'location suburban|quartier|vorort|wohnquartier'},
 'location_urban_city_center': {'neg': 'no location urban city center|not '
                                       'location urban city center|kein '
                                       'location urban city center|nicht '
                                       'location urban city center|sans '
                                       'location urban city center|pas de '
                                       'location urban city center|senza '
                                       'location urban city center|nessun '
                                       'location urban city center',
                                'pos': 'location urban city '
                                       'center|zentrum|zentral|mitten in der '
                                       'stadt'},
 'musicians_welcome': {'neg': 'no musicians welcome|not musicians welcome|kein '
                              'musicians welcome|nicht musicians welcome|sans '
                              'musicians welcome|pas de musicians '
                              'welcome|senza musicians welcome|nessun '
                              'musicians welcome',
                       'pos': 'musicians welcome|musiker|instrumente'},
 'orientation_south_facing': {'neg': 'no orientation south facing|not '
                                     'orientation south facing|kein '
                                     'orientation south facing|nicht '
                                     'orientation south facing|sans '
                                     'orientation south facing|pas de '
                                     'orientation south facing|senza '
                                     'orientation south facing|nessun '
                                     'orientation south facing',
                              'pos': 'orientation south '
                                     'facing|s[üu]dausrichtung|s[üu]dseite'},
 'pedestrian_friendly': {'neg': 'no pedestrian friendly|not pedestrian '
                                'friendly|kein pedestrian friendly|nicht '
                                'pedestrian friendly|sans pedestrian '
                                'friendly|pas de pedestrian friendly|senza '
                                'pedestrian friendly|nessun pedestrian '
                                'friendly',
                         'pos': 'pedestrian '
                                'friendly|fussg[äa]ngerzone|autofrei'},
 'price_includes_utilities': {'neg': 'no price includes utilities|not price '
                                     'includes utilities|kein price includes '
                                     'utilities|nicht price includes '
                                     'utilities|sans price includes '
                                     'utilities|pas de price includes '
                                     'utilities|senza price includes '
                                     'utilities|nessun price includes '
                                     'utilities',
                              'pos': 'price includes utilities|inkl\\. '
                                     'nk|inklusive nebenkosten'},
 'prop_garden_private': {'neg': 'no prop garden private|not prop garden '
                                'private|kein prop garden private|nicht prop '
                                'garden private|sans prop garden private|pas '
                                'de prop garden private|senza prop garden '
                                'private|nessun prop garden private',
                         'pos': 'prop garden private|privater garten|eigener '
                                'garten'},
 'prop_garden_shared': {'neg': 'no prop garden shared|not prop garden '
                               'shared|kein prop garden shared|nicht prop '
                               'garden shared|sans prop garden shared|pas de '
                               'prop garden shared|senza prop garden '
                               'shared|nessun prop garden shared',
                        'pos': 'prop garden '
                               'shared|gemeinschaftsgarten|mitbenutzung '
                               'garten'},
 'prop_wintergarden': {'neg': 'no prop wintergarden|not prop wintergarden|kein '
                              'prop wintergarden|nicht prop wintergarden|sans '
                              'prop wintergarden|pas de prop '
                              'wintergarden|senza prop wintergarden|nessun '
                              'prop wintergarden',
                       'pos': 'prop wintergarden|wintergarten'},
 'seniors_preferred': {'neg': 'no seniors preferred|not seniors preferred|kein '
                              'seniors preferred|nicht seniors preferred|sans '
                              'seniors preferred|pas de seniors '
                              'preferred|senza seniors preferred|nessun '
                              'seniors preferred',
                       'pos': 'seniors preferred|senioren|altersgerecht|50\\+'},
 'shares_washing_room': {'neg': 'no shares washing room|not shares washing '
                                'room|kein shares washing room|nicht shares '
                                'washing room|sans shares washing room|pas de '
                                'shares washing room|senza shares washing '
                                'room|nessun shares washing room',
                         'pos': 'shares washing room|mitbenutzung '
                                'waschk[üu]che|gemeinschaftswaschk[üu]che'},
 'smokers_allowed': {'neg': 'no smokers allowed|not smokers allowed|kein '
                            'smokers allowed|nicht smokers allowed|sans '
                            'smokers allowed|pas de smokers allowed|senza '
                            'smokers allowed|nessun smokers allowed',
                     'pos': 'smokers allowed|raucher'},
 'style_industrial_loft': {'neg': 'no style industrial loft|not style '
                                  'industrial loft|kein style industrial '
                                  'loft|nicht style industrial loft|sans style '
                                  'industrial loft|pas de style industrial '
                                  'loft|senza style industrial loft|nessun '
                                  'style industrial loft',
                           'pos': 'style industrial '
                                  'loft|loft|industrie|industrial'},
 'sublease_allowed': {'neg': 'no sublease allowed|not sublease allowed|kein '
                             'sublease allowed|nicht sublease allowed|sans '
                             'sublease allowed|pas de sublease allowed|senza '
                             'sublease allowed|nessun sublease allowed',
                      'pos': 'sublease allowed|untermiete|untervermietung'},
 'suitability_couples': {'neg': 'no suitability couples|not suitability '
                                'couples|kein suitability couples|nicht '
                                'suitability couples|sans suitability '
                                'couples|pas de suitability couples|senza '
                                'suitability couples|nessun suitability '
                                'couples',
                         'pos': 'suitability couples|paare'},
 'suitability_expats': {'neg': 'no suitability expats|not suitability '
                               'expats|kein suitability expats|nicht '
                               'suitability expats|sans suitability expats|pas '
                               'de suitability expats|senza suitability '
                               'expats|nessun suitability expats',
                        'pos': 'suitability expats|expat|international'},
 'suitability_singles': {'neg': 'no suitability singles|not suitability '
                                'singles|kein suitability singles|nicht '
                                'suitability singles|sans suitability '
                                'singles|pas de suitability singles|senza '
                                'suitability singles|nessun suitability '
                                'singles',
                         'pos': 'suitability singles|single|f[üu]r eine '
                                'person'},
 'suitability_students': {'neg': 'no suitability students|not suitability '
                                 'students|kein suitability students|nicht '
                                 'suitability students|sans suitability '
                                 'students|pas de suitability students|senza '
                                 'suitability students|nessun suitability '
                                 'students',
                          'pos': 'suitability '
                                 'students|wg|studenten|wohngemeinschaft'},
 'surroundings_forest': {'neg': 'no surroundings forest|not surroundings '
                                'forest|kein surroundings forest|nicht '
                                'surroundings forest|sans surroundings '
                                'forest|pas de surroundings forest|senza '
                                'surroundings forest|nessun surroundings '
                                'forest',
                         'pos': 'surroundings forest|waldrand|wald'},
 'surroundings_parks': {'neg': 'no surroundings parks|not surroundings '
                               'parks|kein surroundings parks|nicht '
                               'surroundings parks|sans surroundings parks|pas '
                               'de surroundings parks|senza surroundings '
                               'parks|nessun surroundings parks',
                        'pos': 'surroundings parks|park|gr[üu]nanlage'},
 'surroundings_water': {'neg': 'no surroundings water|not surroundings '
                               'water|kein surroundings water|nicht '
                               'surroundings water|sans surroundings water|pas '
                               'de surroundings water|senza surroundings '
                               'water|nessun surroundings water',
                        'pos': 'surroundings water|fluss|bach|gew[äa]sser|nah '
                               'am see'},
 'vibe_breathtaking_view': {'neg': 'no vibe breathtaking view|not vibe '
                                   'breathtaking view|kein vibe breathtaking '
                                   'view|nicht vibe breathtaking view|sans '
                                   'vibe breathtaking view|pas de vibe '
                                   'breathtaking view|senza vibe breathtaking '
                                   'view|nessun vibe breathtaking view',
                            'pos': 'vibe breathtaking view|traumhafte '
                                   'aussicht|weitsicht'},
 'vibe_bright_light': {'neg': 'no vibe bright light|not vibe bright light|kein '
                              'vibe bright light|nicht vibe bright light|sans '
                              'vibe bright light|pas de vibe bright '
                              'light|senza vibe bright light|nessun vibe '
                              'bright light',
                       'pos': 'vibe bright '
                              'light|hell|lichtdurchflutet|sonnenverw[öo]hnt|bright'},
 'vibe_charming_neighborhood': {'neg': 'no vibe charming neighborhood|not vibe '
                                       'charming neighborhood|kein vibe '
                                       'charming neighborhood|nicht vibe '
                                       'charming neighborhood|sans vibe '
                                       'charming neighborhood|pas de vibe '
                                       'charming neighborhood|senza vibe '
                                       'charming neighborhood|nessun vibe '
                                       'charming neighborhood',
                                'pos': 'vibe charming neighborhood|charmantes '
                                       'quartier'},
 'vibe_compact': {'neg': 'no vibe compact|not vibe compact|kein vibe '
                         'compact|nicht vibe compact|sans vibe compact|pas de '
                         'vibe compact|senza vibe compact|nessun vibe compact',
                  'pos': 'vibe compact|kompakt|klein aber fein'},
 'vibe_cozy': {'neg': 'no vibe cozy|not vibe cozy|kein vibe cozy|nicht vibe '
                      'cozy|sans vibe cozy|pas de vibe cozy|senza vibe '
                      'cozy|nessun vibe cozy',
               'pos': 'vibe cozy|gem[uü]tlich|heimelig|cozy'},
 'vibe_extravagant': {'neg': 'no vibe extravagant|not vibe extravagant|kein '
                             'vibe extravagant|nicht vibe extravagant|sans '
                             'vibe extravagant|pas de vibe extravagant|senza '
                             'vibe extravagant|nessun vibe extravagant',
                      'pos': 'vibe '
                             'extravagant|extravagant|aussergew[öo]hnlich|speziell'},
 'vibe_family_friendly': {'neg': 'no vibe family friendly|not vibe family '
                                 'friendly|kein vibe family friendly|nicht '
                                 'vibe family friendly|sans vibe family '
                                 'friendly|pas de vibe family friendly|senza '
                                 'vibe family friendly|nessun vibe family '
                                 'friendly',
                          'pos': 'vibe family '
                                 'friendly|familienfreundlich|kindergerecht'},
 'vibe_historic_charming': {'neg': 'no vibe historic charming|not vibe '
                                   'historic charming|kein vibe historic '
                                   'charming|nicht vibe historic charming|sans '
                                   'vibe historic charming|pas de vibe '
                                   'historic charming|senza vibe historic '
                                   'charming|nessun vibe historic charming',
                            'pos': 'vibe historic '
                                   'charming|historisch|altbau|charmant|charme'},
 'vibe_luxury_premium': {'neg': 'no vibe luxury premium|not vibe luxury '
                                'premium|kein vibe luxury premium|nicht vibe '
                                'luxury premium|sans vibe luxury premium|pas '
                                'de vibe luxury premium|senza vibe luxury '
                                'premium|nessun vibe luxury premium',
                         'pos': 'vibe luxury '
                                'premium|luxuri[öo]s|exklusiv|hochwertig|premium'},
 'vibe_modern': {'neg': 'no vibe modern|not vibe modern|kein vibe modern|nicht '
                        'vibe modern|sans vibe modern|pas de vibe modern|senza '
                        'vibe modern|nessun vibe modern',
                 'pos': 'vibe modern|modern|neu|zeitgem[äa]ss'},
 'vibe_quiet_peaceful': {'neg': 'no vibe quiet peaceful|not vibe quiet '
                                'peaceful|kein vibe quiet peaceful|nicht vibe '
                                'quiet peaceful|sans vibe quiet peaceful|pas '
                                'de vibe quiet peaceful|senza vibe quiet '
                                'peaceful|nessun vibe quiet peaceful',
                         'pos': 'vibe quiet '
                                'peaceful|ruhig|friedlich|idyllisch|quiet'},
 'vibe_spacious': {'neg': 'no vibe spacious|not vibe spacious|kein vibe '
                          'spacious|nicht vibe spacious|sans vibe spacious|pas '
                          'de vibe spacious|senza vibe spacious|nessun vibe '
                          'spacious',
                   'pos': 'vibe '
                          'spacious|grossz[üu]gig|weitl[äa]ufig|ger[äa]umig|spacious'},
 'vibe_student_budget': {'neg': 'no vibe student budget|not vibe student '
                                'budget|kein vibe student budget|nicht vibe '
                                'student budget|sans vibe student budget|pas '
                                'de vibe student budget|senza vibe student '
                                'budget|nessun vibe student budget',
                         'pos': 'vibe student '
                                'budget|student|g[üu]nstig|preiswert'},
 'vibe_sunny': {'neg': 'no vibe sunny|not vibe sunny|kein vibe sunny|nicht '
                       'vibe sunny|sans vibe sunny|pas de vibe sunny|senza '
                       'vibe sunny|nessun vibe sunny',
                'pos': 'vibe sunny|sonnig|besonnt'},
 'view_city': {'neg': 'no view city|not view city|kein view city|nicht view '
                      'city|sans view city|pas de view city|senza view '
                      'city|nessun view city',
               'pos': 'view city|stadtsicht|blick [üu]ber die stadt'},
 'view_lake': {'neg': 'no view lake|not view lake|kein view lake|nicht view '
                      'lake|sans view lake|pas de view lake|senza view '
                      'lake|nessun view lake',
               'pos': 'view lake|seesicht|blick auf den see|lake view'},
 'view_mountains': {'neg': 'no view mountains|not view mountains|kein view '
                           'mountains|nicht view mountains|sans view '
                           'mountains|pas de view mountains|senza view '
                           'mountains|nessun view mountains',
                    'pos': 'view mountains|bergsicht|alpenblick|blick auf die '
                           'alpen|mountain view'},
 'view_nature': {'neg': 'no view nature|not view nature|kein view nature|nicht '
                        'view nature|sans view nature|pas de view nature|senza '
                        'view nature|nessun view nature',
                 'pos': 'view nature|ins gr[üu]ne|natur|b[äa]ume'}}

def extract_boolean(text_series, pos_regex, neg_regex):
    matches_neg = text_series.str.contains(neg_regex, case=False, regex=True, na=False)
    matches_pos = text_series.str.contains(pos_regex, case=False, regex=True, na=False)
    
    result = pd.Series(pd.NA, index=text_series.index, dtype=pd.BooleanDtype())
    result[matches_pos] = True
    result[matches_neg] = False  # Negation overrides positive if both exist
    
    return result

def generate_apartment_attributes(input_file=None, output_file=None, fill_na_false=False):
    if input_file is None:
        input_file = os.path.join(current_dir, "structured_data_withoutimages-1776412361239.csv")
    if output_file is None:
        output_file = os.path.join(current_dir, "apartment_features_134.pkl")
        
    print(f"Loading {input_file}...")
    df = pd.read_csv(input_file, encoding='utf-8-sig')

    features = pd.DataFrame(index=df.index)

    # Convert all text into a single lowercase column for NLP searching
    text_content = (df['title'].fillna('') + ' ' + df['object_description'].fillna('') + ' ' + df.get('remarks', pd.Series('')).fillna('')).str.lower()

    # Numeric features
    def map_numeric(col):
        if col in df.columns:
            return pd.to_numeric(df[col], errors='coerce')
        return pd.Series(pd.NA, index=df.index, dtype='float64')

    numeric_cols = ['price', 'area', 'number_of_rooms', 'floor', 'year_built', 
                    'geo_lat', 'geo_lng', 'distance_public_transport', 'distance_shop', 
                    'distance_kindergarten', 'distance_school_1', 'distance_school_2']
    
    for c in numeric_cols:
        features[c] = map_numeric(c)

    # Base Text/Category CSV Features
    features['offer_type'] = df.get('offer_type', pd.Series(pd.NA, index=df.index)).astype('string')
    features['maybe_temporary'] = df.get('maybe_temporary', pd.Series(pd.NA, index=df.index)).astype('string')
    features['object_street'] = df.get('object_street', pd.Series(pd.NA, index=df.index)).astype('string')
    features['object_zip'] = df.get('object_zip', pd.Series(pd.NA, index=df.index)).astype('string')
    features['object_city'] = df.get('object_city', pd.Series(pd.NA, index=df.index)).astype('string')
    features['object_state'] = df.get('object_state', pd.Series(pd.NA, index=df.index)).astype('string')
    features['object_type'] = df.get('object_type', df.get('object_type_text', pd.Series(pd.NA, index=df.index))).astype('string')

    # Base Boolean CSV Features
    def map_bool(col):
        if col in df.columns:
            s_str = df[col].astype(str).str.lower()
            res = pd.Series(pd.NA, index=df.index, dtype=pd.BooleanDtype())
            res[s_str.isin(['1', '1.0', 'true', 'yes', 'y'])] = True
            res[s_str.isin(['0', '0.0', 'false', 'no', 'n'])] = False
            return res
        return pd.Series(pd.NA, index=df.index, dtype=pd.BooleanDtype())

    csv_bool_cols = ['is_new_building', 'prop_fireplace', 'prop_balcony', 'prop_elevator', 
                     'prop_parking', 'prop_garage', 'animal_allowed', 'prop_child_friendly']
    for c in csv_bool_cols:
         features[c] = map_bool(c)

    # Now execute the NLP generator engine for the 107 GEN features
    f_dict = feature_dictionary()
    for feat_name, rules in f_dict.items():
        features[feat_name] = extract_boolean(text_content, rules['pos'], rules['neg'])

    # Fill NA False option
    if fill_na_false:
        for c in features.columns:
            if isinstance(features[c].dtype, pd.core.dtypes.dtypes.BooleanDtype) or str(features[c].dtype) == 'boolean':
                features[c] = features[c].fillna(False)
            elif features[c].dtype == 'float64':
                features[c] = features[c].fillna(0.0)

    # Validation
    final_count = len(features.columns)
    print(f"Generated {final_count} features.")
    
    df_final = pd.concat([df[['id']], features], axis=1)
    df_final.to_pickle(output_file)
    print(f"Saved exact {final_count}-dim features mapping to {output_file}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Preprocess apartments data")
    parser.add_argument('--sample-csvs', action='store_true', help="Sample CSVs")
    parser.add_argument('--sample-headers', action='store_true', help="Sample headers")
    parser.add_argument('--generate', action='store_true', help="Generate apartment features (default)")
    parser.add_argument('--fill-na-false', action='store_true', help="Fill NULL boolean values with False")
    
    args = parser.parse_args()

    if not (args.sample_csvs or args.sample_headers or args.generate):
        args.generate = True

    if args.sample_csvs:
        print(json.dumps(sample_csvs(), indent=2))
    elif args.sample_headers:
        print(json.dumps(sample_headers(), indent=2))
    elif args.generate:
        generate_apartment_attributes(fill_na_false=args.fill_na_false)
